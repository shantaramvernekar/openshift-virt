#!/usr/bin/env python3
"""Check repository examples without contacting infrastructure."""
import ipaddress
import json
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

import yaml

REPO = Path(__file__).resolve().parents[1]


def load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def check_renderer(inventory):
    with tempfile.TemporaryDirectory(prefix="openshift-virt-check-") as directory:
        root = Path(directory)
        secrets = {
            name: {"username": "mock:user", "password": "mock: '# has quotes"}
            for name, *_ in inventory["hosts"]
        }
        pull_secret = {"auths": {"registry.example.test": {"auth": "ZHVtbXk6ZHVtbXk="}}}
        dump_json(root / "bmc.json", secrets)
        dump_json(root / "pull.json", pull_secret)
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(root / "dummy-key")],
            check=True,
        )
        output = root / "install"
        command = [
            sys.executable, str(REPO / "scripts/render-install-config.py"),
            "--template", str(REPO / "config/install-config.yaml.template"),
            "--bmc-credentials", str(root / "bmc.json"),
            "--pull-secret", str(root / "pull.json"),
            "--ssh-key", str(root / "dummy-key.pub"),
            "--output-dir", str(output),
        ]
        first = subprocess.run(command, check=True, text=True, capture_output=True)
        assert "mock" not in first.stdout + first.stderr
        path = output / "install-config.yaml"
        assert stat.S_IMODE(output.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        rendered = load_yaml(path)
        assert "__RENDER_" not in path.read_text(encoding="utf-8")
        for host in rendered["platform"]["baremetal"]["hosts"]:
            for key, value in secrets[host["name"]].items():
                assert host["bmc"][key] == value
        assert json.loads(rendered["pullSecret"]) == pull_secret
        assert rendered["sshKey"] == (root / "dummy-key.pub").read_text().strip()

        before = path.read_bytes()
        rerun = subprocess.run(command, text=True, capture_output=True)
        assert rerun.returncode != 0 and path.read_bytes() == before
        (root / "bmc.json").chmod(0o644)
        loose = subprocess.run(
            [*command[:-1], str(root / "loose")], text=True, capture_output=True
        )
        assert loose.returncode != 0 and not (root / "loose").exists()
        assert "mock" not in rerun.stdout + rerun.stderr + loose.stdout + loose.stderr
        return rendered


def check_inventory(inventory, config):
    baremetal = config["platform"]["baremetal"]
    addresses = inventory["addresses"]
    networks = {key: ipaddress.ip_network(value) for key, value in inventory["networks"].items()}
    assert f"{config['metadata']['name']}.{config['baseDomain']}" == inventory["cluster"]
    assert baremetal["provisioningNetwork"] == "Disabled"
    assert baremetal["externalMACAddress"] == inventory["bootstrapMAC"]
    assert baremetal["clusterProvisioningIP"] == addresses["clusterProvisioning"]
    assert baremetal["apiVIPs"] == [addresses["api"]]
    assert baremetal["ingressVIPs"] == [addresses["ingress"]]
    assert baremetal["additionalNTPServers"] == [addresses["ntp"]]
    assert config["networking"]["machineNetwork"] == [{"cidr": str(networks["machine"])}]
    assert config["networking"]["clusterNetwork"] == [{"cidr": str(networks["pods"]), "hostPrefix": 23}]
    assert config["networking"]["serviceNetwork"] == [str(networks["services"])]
    host_rows = inventory["hosts"]
    hosts = baremetal["hosts"]
    assert len(host_rows) == len(hosts) == 6
    assert sum(host["role"] == "master" for host in hosts) == config["controlPlane"]["replicas"] == 3
    assert sum(host["role"] == "worker" for host in hosts) == config["compute"][0]["replicas"] == 3
    node_ips = [*addresses.values(), *(row[2] for row in host_rows)]
    assert len(set(node_ips)) == len(node_ips)
    assert len({row[3] for row in host_rows}) == len({row[4] for row in host_rows}) == len(hosts)
    assert len({row[5] for row in host_rows}) == len(hosts)
    assert all(ipaddress.ip_address(value) in networks["machine"] for value in node_ips)

    preflight = (REPO / "runbooks/01-preflight.md").read_text(encoding="utf-8")
    topology = (REPO / "diagrams/README.md").read_text(encoding="utf-8")
    for name, role, node, bmc, mac, serial in host_rows:
        host = next(item for item in hosts if item["name"] == name)
        assert host["role"] == role and host["bootMACAddress"] == mac
        assert host["bmc"]["address"] == f"redfish-virtualmedia://{bmc}/redfish/v1/Systems/1"
        assert host["rootDeviceHints"]["serialNumber"] == serial
        assert ipaddress.ip_address(bmc) in networks["bmc"]
        display_role = "control plane" if role == "master" else "worker"
        assert f"| {name} | {display_role} | {node} | {bmc} | {mac} | {serial} |" in preflight
        assert f"{name} .{node.rsplit('.', 1)[1]}" in topology
    for address in addresses.values():
        assert address in preflight


def check_examples(dummy_key):
    resources = []
    for path in sorted((REPO / "examples").rglob("*.yaml")):
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        assert all(doc.get("apiVersion") and doc.get("kind") for doc in docs), path
        resources.extend(docs)
    vm = next(doc for doc in resources if doc["kind"] == "VirtualMachine")
    volume = vm["spec"]["dataVolumeTemplates"][0]
    vm_template = vm["spec"]["template"]
    assert vm_template["spec"]["volumes"][0]["dataVolume"]["name"] == volume["metadata"]["name"]
    user_data = vm_template["spec"]["volumes"][1]["cloudInitNoCloud"]["userData"]
    cloud_init = yaml.safe_load(user_data.replace("REPLACE_WITH_LAB_OPENSSH_PUBLIC_KEY", dummy_key))
    assert cloud_init["users"][1]["ssh_authorized_keys"] == [dummy_key]
    nad = next(doc for doc in resources if doc["kind"] == "NetworkAttachmentDefinition")
    bridge_policy = next(doc for doc in resources if doc["kind"] == "NodeNetworkConfigurationPolicy")
    assert json.loads(nad["spec"]["config"])["bridge"] == (
        bridge_policy["spec"]["desiredState"]["interfaces"][0]["name"]
    )
    migration = next(doc for doc in resources if doc["kind"] == "VirtualMachineInstanceMigration")
    assert migration["spec"]["vmiName"] == vm["metadata"]["name"]
    assert migration["metadata"]["namespace"] == vm["metadata"]["namespace"]
    for route in (doc for doc in resources if doc["kind"] == "Route"):
        namespace = route["metadata"]["namespace"]
        service = next(
            doc for doc in resources
            if doc["kind"] == "Service"
            and doc["metadata"]["namespace"] == namespace
            and doc["metadata"]["name"] == route["spec"]["to"]["name"]
        )
        assert route["spec"]["port"]["targetPort"] in (
            port["name"] for port in service["spec"]["ports"]
        )
        assert route["spec"]["host"].endswith(".apps.virt-lab.example.test")
    return len(resources)


def check_markdown():
    snippets = 0
    links = 0
    documents = [REPO / "README.md"]
    for group in ("runbooks", "diagrams", "examples"):
        documents.extend((REPO / group).rglob("*.md"))
    for path in sorted(documents):
        contents = path.read_text(encoding="utf-8")
        for block in re.findall(r"```bash\n(.*?)```", contents, flags=re.DOTALL):
            subprocess.run(["bash", "-n"], input=block, text=True, check=True)
            snippets += 1
        for block in re.findall(r"```yaml\n(.*?)```", contents, flags=re.DOTALL):
            assert list(yaml.safe_load_all(block)), path
        for link in re.findall(r"\]\(([^)]+)\)", contents):
            if link.startswith(("http:", "https:", "mailto:")):
                continue
            target, _, anchor = unquote(link).partition("#")
            dest = path.parent / target if target else path
            assert dest.exists(), (path, link)
            if anchor and dest.suffix == ".md":
                headings = re.findall(r"^#+\s+(.+)$", dest.read_text(), flags=re.MULTILINE)
                anchors = {
                    re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
                    for heading in headings
                }
                assert anchor in anchors, (path, link)
            links += 1
    subprocess.run(["bash", "-n", REPO / "scripts/preflight.sh"], check=True)
    return snippets, links


def main():
    inventory = load_yaml(REPO / "config/inventory.yaml")
    install_config = check_renderer(inventory)
    check_inventory(inventory, install_config)
    resources = check_examples(install_config["sshKey"])
    snippets, links = check_markdown()
    print("PASS dummy renderer, private modes, output reuse rejection, and six-host inventory")
    print(f"PASS {resources} resource documents, guest cloud-init, and CNI JSON")
    print(f"PASS preflight shell syntax, {snippets} Bash blocks, and {links} local Markdown links")


if __name__ == "__main__":
    main()
