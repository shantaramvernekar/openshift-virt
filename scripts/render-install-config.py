#!/usr/bin/env python3
"""Render a bare-metal install config into a new private directory."""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml


class InputError(Exception):
    pass


def read_private_json(path):
    with path.open(encoding="utf-8") as stream:
        if os.fstat(stream.fileno()).st_mode & 0o077:
            raise InputError("Pull secret and BMC credentials must have mode 0600 or stricter.")
        return json.load(stream)


def render(args):
    config = yaml.safe_load(args.template.read_text(encoding="utf-8"))
    credentials = read_private_json(args.bmc_credentials)
    pull_secret = read_private_json(args.pull_secret)
    ssh_key = args.ssh_key.read_text(encoding="utf-8").strip()
    if not isinstance(pull_secret.get("auths"), dict) or not pull_secret["auths"]:
        raise InputError("The pull secret needs a nonempty auths object.")
    if not ssh_key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")) or "\n" in ssh_key:
        raise InputError("Supply one OpenSSH public key.")

    hosts = config["platform"]["baremetal"]["hosts"]
    if set(credentials) != {host["name"] for host in hosts}:
        raise InputError("BMC credential names must match all template host names.")
    for host in hosts:
        entry = credentials[host["name"]]
        for key in ("username", "password"):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise InputError("Every host needs a nonempty BMC username and password.")
            host["bmc"][key] = entry[key]
    config["sshKey"] = ssh_key
    config["pullSecret"] = json.dumps(pull_secret, separators=(",", ":"))
    rendered = yaml.safe_dump(config, sort_keys=False)

    # A new directory prevents accidental overwrite or reuse of installer state.
    os.umask(0o077)
    args.output_dir.mkdir(mode=0o700)
    with (args.output_dir / "install-config.yaml").open("x", encoding="utf-8") as stream:
        stream.write(rendered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--bmc-credentials", type=Path, required=True)
    parser.add_argument("--pull-secret", type=Path, required=True)
    parser.add_argument("--ssh-key", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        render(args)
    except InputError as error:
        parser.exit(1, f"Render failed. {error}\n")
    except FileExistsError:
        parser.exit(1, "Render failed. Choose a new output directory.\n")
    except (OSError, ValueError, yaml.YAMLError, KeyError, TypeError, AttributeError):
        parser.exit(1, "Render failed. Check input paths, permissions, and file structure.\n")
    print("Wrote install-config.yaml in the private output directory.")


if __name__ == "__main__":
    main()
