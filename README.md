# Bare-metal OpenShift Virtualization with IPI

An installation walkthrough for OpenShift Container Platform 4.20 (x86_64). The reference cluster, `virt-lab.example.test`, uses a RHEL 9 provisioner, three physical control-plane servers, three physical RHCOS workers, and HPE iLO virtual media. It uses site DHCP on the machine network, cluster-managed API and ingress VIPs, and a connected release registry. All inventory values are fictional.

## Installation at a glance

| Step | What happens | Evidence |
| --- | --- | --- |
| 1. Prepare | Reserve seven DHCP leases, three service addresses, and six BMC endpoints. Verify bridge, boot NICs, disks, firmware, and both directions of virtual-media traffic. | Approved inventory, DNS, DHCP, routing and firmware checks |
| 2. Configure | Extract the installer from the selected 4.20 payload. Render the six-host install config privately. | Installer version and payload digest, reviewed configuration |
| 3. Bootstrap | The installer uses system libvirt on the provisioner to launch a temporary RHCOS VM. Bootstrap brings up the temporary control plane, Machine Config Server, and provisioning services. | Domain, bridged NIC and bootstrap service logs |
| 4. Provision control plane | BMO reconciles each BareMetalHost. Ironic directs iLO to attach an ISO. IPA runs on the physical host and deploys RHCOS. On disk boot, Ignition gets role configuration and kubelet starts. | BMC virtual-media status, Ironic/IPA logs, MCS fetch and node registration |
| 5. Hand off and accept | The provisioner removes the bootstrap VM after bootstrap completes. The permanent control plane serves the API and runs Metal³ to provision workers. | Six Ready nodes, healthy Operators and pools, successful external Route |
| 6. Enable virtualization | Install the OpenShift Virtualization Operator and then its HyperConverged resource. Run a persistent VM and prove restart and eligible live migration. | KVM capacity, CDI import, guest network, restart marker and migration status |

## Reading path

1. [Physical environment and preflight](runbooks/01-preflight.md)
2. [Installer and private configuration](runbooks/02-installer-config.md)
3. [Bootstrap VM and installation artifacts](runbooks/03-bootstrap.md)
4. [Follow master-0 from power-off](runbooks/04-physical-host.md)
5. [Handoff, worker-0 and cluster acceptance](runbooks/05-acceptance.md)
6. [OpenShift Virtualization and guest validation](runbooks/06-virtualization.md)
7. [Disconnected installation differences](runbooks/07-disconnected.md), [command cheat sheet](runbooks/commands.md), and [troubleshooting](runbooks/troubleshooting.md)

[Editable diagrams](diagrams/README.md) cover all stages. [Source review and validation](runbooks/validation.md) records reference corrections, local checks and live acceptance gates. Commands that change infrastructure or cluster state are marked in the runbooks and intended for an authorized installation window.
