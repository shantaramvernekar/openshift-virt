# 3. Launch and inspect the bootstrap VM

## Three separate artifacts

| Artifact | Default source in 4.20 | Consumer and purpose | Override or site control |
| --- | --- | --- | --- |
| RHCOS QEMU disk (`qcow2.gz`) | Installer's embedded RHCOS stream metadata identifies the external QEMU artifact | Installer on the RHEL provisioner imports the base image into a libvirt disk for the RHCOS bootstrap guest | `platform.baremetal.bootstrapOSImage` with the uncompressed SHA-256 |
| Virtual-media boot ISO | The 4.20 provisioning stack extracts base assets from the payload's `machine-os-images` component and prepares a host-specific boot ISO using the payload's `ironic-agent` component and image customization controller. | iLO fetches the prepared ISO over the media-serving network and exposes it as a virtual drive. Physical firmware boots it and IPA starts. | Connected template uses the payload default. Day-2 `Provisioning.spec.preProvisioningOSDownloadURLs.isoURL` specifies the preprovisioning source where supported by the actual provisioning configuration. It differs from the per-host URL Ironic generates. |
| RHCOS installation image | The matched payload's `machine-os-images` component supplies the default RHCOS metal disk image | Target node's IPA deploys RHCOS on the selected physical disk | The 4.20 installer type still exposes `platform.baremetal.clusterOSImage` for a URL with SHA-256. Leave it unset for the default; confirm support for an override on the exact patch and site before using it. |

[OCP 4.20 IPI workflow and image cache](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [4.20 provisioning APIs](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/provisioning_apis/provisioning-metal3-io-v1alpha1), [4.20 payload image selection and extraction](https://github.com/openshift/installer/blob/release-4.20/data/data/bootstrap/baremetal/files/usr/local/bin/build-ironic-env.sh), [4.20 image customization](https://github.com/openshift/installer/blob/release-4.20/data/data/bootstrap/baremetal/files/etc/containers/systemd/image-customization.container), [Installer 4.20 bare-metal types](https://github.com/openshift/installer/blob/release-4.20/pkg/types/baremetal/platform.go)

## Start the install

On the **RHEL provisioner**, after reviewing the six BMC and disk mappings and confirming the installation window, run the following. The command can reboot the six targets and write their installation disks.

```bash
umask 077
openshift-baremetal-install --dir "$INSTALL_DIR" --log-level=info create cluster
```

The installer transforms install configuration into manifests and then bootstrap, control-plane and worker Ignition assets. The bootstrap config starts the temporary services. The role stubs direct physical machines to their role configuration. For deliberate installer-time customization, first run `openshift-baremetal-install --dir "$INSTALL_DIR" create manifests` on the provisioner, put only supported additions into the generated manifest directories, review them, and run the same `create cluster` against that directory. The normal IPI command handles asset generation and provisioning itself. Keep time-sensitive assets private and generate them close to installation. [OCP 4.20 installation workflow and deployment steps, section 3.4](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)

| Location | Responsibility |
| --- | --- |
| RHEL provisioner | Runs the installer, accesses release and image artifacts, hosts system libvirt/KVM and the Linux bridge, and orchestrates creation and removal of the bootstrap domain. |
| RHCOS bootstrap VM | Boots with its own Ignition, brings up the temporary control plane and Machine Config Server, and runs bootstrap Metal³ components including BMO, Ironic and image/ISO-serving containers. |
| Physical nodes | iLO mounts media outside the node OS. The host runs IPA from the live ISO and boots RHCOS from its installed disk. |

## Read-only observation

On the **RHEL provisioner** in a second shell, set `INSTALL_DIR` to the same private directory and use the name shown by `virsh list --all` for `BOOTSTRAP_DOMAIN`. Check the bridge and guest address before connecting.

```bash
virsh -c qemu:///system list --all
virsh -c qemu:///system domblklist "$BOOTSTRAP_DOMAIN" --details
virsh -c qemu:///system domiflist "$BOOTSTRAP_DOMAIN"
virsh -c qemu:///system console "$BOOTSTRAP_DOMAIN"
journalctl -u libvirtd -u virtqemud --since '-30 min'
tail -n 100 "$INSTALL_DIR/.openshift_install.log"
ssh core@192.0.2.20
```

Use Ctrl+] to exit the console. The active libvirt unit depends on the RHEL setup. Within the **bootstrap VM**, inspect service logs and discover active containers from real names.

```bash
sudo journalctl -b -u release-image.service -u bootkube.service -u kubelet.service
sudo journalctl -b -u extract-machine-os.service -u ironic.service -u metal3-baremetal-operator.service
sudo podman ps -a --format '{{.Names}} {{.Status}}'
sudo crictl ps -a
sudo ss -lntp
```

A **running VM** means the hypervisor started the guest. **Bootstrap complete** means the permanent control plane has reached the handoff milestone and can carry on without bootstrap. **Installation complete** is the later installer milestone, followed by the [acceptance checks](05-acceptance.md). Observe either wait command from the provisioner using the same state directory if needed. [OCP 4.20 bootstrap and troubleshooting, sections 3.2.11 and 3.5.3](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)
