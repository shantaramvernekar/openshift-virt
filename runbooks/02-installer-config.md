# 2. Installer and configuration

## Pin and extract the release

On the **RHEL provisioner**, use an x86_64 Linux `oc`, `curl`, `tar` and `jq`. Choose and record the approved 4.20 patch before running these commands. The mirror's `release.txt` supplies the payload pullspec. Record the pullspec and the output of `version` with the change.

```bash
umask 077
: "${OCP_VERSION:?Set OCP_VERSION to the approved 4.20.z patch}"
release_dir="https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/$OCP_VERSION"
release_metadata=$(curl -fsSL "$release_dir/release.txt")
release_image=$(awk '/^Pull From: quay\.io/ { print $3; exit }' <<< "$release_metadata")
test -n "$release_image" || exit 1
mkdir -p "$HOME/ocp-tools/$OCP_VERSION"
cd "$HOME/ocp-tools/$OCP_VERSION" || exit 1
curl -fsSLO "$release_dir/openshift-client-linux.tar.gz"
tar -xzf openshift-client-linux.tar.gz oc
./oc adm release extract --registry-config "$HOME/ocp-private/pull-secret.json" \
  --command=openshift-baremetal-install --to "$PWD" "$release_image"
./openshift-baremetal-install version
./openshift-baremetal-install coreos print-stream-json |
  jq -er '.architectures.x86_64.artifacts.qemu.formats["qcow2.gz"].disk.location'
export PATH="$PWD:$PATH"
```

The Kubernetes architecture field is `amd64`. The RHCOS stream metadata and mirror path use `x86_64`. Pin a specific patch for repeatability. [OCP 4.20 IPI installer extraction and RHCOS cache, sections 3.3.8–3.3.10](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)

## Render a private config

The [six-host template](../config/install-config.yaml.template) uses `platform.baremetal`, `provisioningNetwork: Disabled` and the plural VIP fields. Site DHCP gives 192.0.2.20 to the bootstrap VM identified by `externalMACAddress`. The six physical servers have their own site reservations, and `clusterProvisioningIP` gives the permanent service its own 192.0.2.21 address. The bootstrap VM's address and the cluster provisioning service address satisfy the two-address design. `Managed` is the installer default for the provisioning network, so `Disabled` is explicit. `baremetal` is the default bridge name, and `UEFI` and `default` are the installer defaults for boot mode and hardware profile. `bootstrapProvisioningIP` is for the dedicated provisioning network.

If the bootstrap guest needs static addressing, use this addition under `platform.baremetal`. Keep the bootstrap IP outside DHCP allocations and leave node DHCP reservations in place if the node network still uses DHCP. On a fully DHCP-free site, also provide per-host `networkConfig` in NMState format for the live boot and installed host, with site NIC/MAC, IP and prefix, route and DNS. Set `bootMACAddress` to the correct host interface in either design.

```yaml
bootstrapExternalStaticIP: 192.0.2.20
bootstrapExternalStaticGateway: 192.0.2.1
bootstrapExternalStaticDNS: 192.0.2.53
```

The equivalent Dell host changes the `address` scheme and Redfish system path while keeping the same BMC management address if inventory reassigns it to a Dell server. Supply Dell credentials and validate the firmware and AutoAttach setting. The certificate setting follows the actual trust policy.

```yaml
bmc:
  address: idrac-virtualmedia://198.51.100.11/redfish/v1/Systems/System.Embedded.1
  username: "__RENDER_BMC_USERNAME__"
  password: "__RENDER_BMC_PASSWORD__"
  disableCertificateVerification: false
```

[OCP 4.20 host addressing, root device hints and config parameters, sections 3.3.14 and 3.3.17](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [Installer 4.20 bare-metal types and defaults](https://github.com/openshift/installer/tree/release-4.20/pkg/types/baremetal)

On the **RHEL provisioner**, prepare a private directory and use Python 3 with PyYAML (`python3-pyyaml` where available). Save a copy of the template there and edit for the actual site. Save the registry pull secret from the Red Hat OpenShift Cluster Manager in JSON format and supply one OpenSSH public key. The BMC credential file is a JSON object keyed by all six host names, with values of the form `{"username":"example-user","password":"example-password"}`. Use a secret manager or private editor to create the JSON. Place both secret input files under `$HOME/ocp-private` with mode 0600 or stricter.

```bash
export REPO="$HOME/openshift-virt"  # Path to this checkout on the provisioner
install -d -m 0700 "$HOME/ocp-private"
cp "$REPO/config/install-config.yaml.template" "$HOME/ocp-private/site-template.yaml"
# Edit site-template.yaml and populate the two private JSON files.
export INSTALL_DIR="$HOME/ocp-private/virt-lab-install"
python3 "$REPO/scripts/render-install-config.py" \
  --template "$HOME/ocp-private/site-template.yaml" \
  --bmc-credentials "$HOME/ocp-private/bmc-credentials.json" \
  --pull-secret "$HOME/ocp-private/pull-secret.json" \
  --ssh-key "$HOME/.ssh/id_ed25519.pub" \
  --output-dir "$INSTALL_DIR"
cp "$INSTALL_DIR/install-config.yaml" "$HOME/ocp-private/virt-lab-install-config.backup"
```

The renderer parses YAML and inserts secret values as strings. The installer consumes concrete YAML values. Output is a newly created 0700 directory with a 0600 file. The script prints a generic error on malformed input, mismatched credentials, loose permissions, or a reused directory. Use a new empty state directory for a new install and preserve the protected backup because the installer consumes `install-config.yaml`. Installer logs, Ignition, assets, credentials, and kubeconfigs belong in the private directory throughout the install.
