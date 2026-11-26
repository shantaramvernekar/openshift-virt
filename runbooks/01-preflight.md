# 1. Physical environment and preflight

Inventory lives in [inventory.yaml](../config/inventory.yaml). The [topology diagram](../diagrams/README.md#topology) shows both routed networks. Reserve node addresses and stable names in forward and reverse DNS. Use DHCP reservations for the physical boot MACs and for the bootstrap guest MAC. If DHCP keys on client identifiers, verify the intended lease during both the live and installed boot. No DHCP or PXE service is supplied by IPI in this example.

| Host | Role | Node or guest IPv4 | HPE iLO IPv4 | Host boot MAC | Root disk serial |
| --- | --- | --- | --- | --- | --- |
| master-0 | control plane | 192.0.2.41 | 198.51.100.11 | 02:00:00:00:00:01 | LAB-master-0-OS |
| master-1 | control plane | 192.0.2.42 | 198.51.100.12 | 02:00:00:00:00:02 | LAB-master-1-OS |
| master-2 | control plane | 192.0.2.43 | 198.51.100.13 | 02:00:00:00:00:03 | LAB-master-2-OS |
| worker-0 | worker | 192.0.2.44 | 198.51.100.14 | 02:00:00:00:00:04 | LAB-worker-0-OS |
| worker-1 | worker | 192.0.2.45 | 198.51.100.15 | 02:00:00:00:00:05 | LAB-worker-1-OS |
| worker-2 | worker | 192.0.2.46 | 198.51.100.16 | 02:00:00:00:00:06 | LAB-worker-2-OS |

| Network or address | Assignment |
| --- | --- |
| 192.0.2.0/24 | Machine network. Gateway 192.0.2.1, DNS 192.0.2.53, NTP 192.0.2.54. |
| 192.0.2.10 | RHEL provisioner, L3 on its Linux bridge `baremetal`. |
| 192.0.2.20 | Temporary bootstrap guest. DHCP reservation for `52:54:00:42:00:20`. |
| 192.0.2.21 | Permanent provisioning service IP. Keep outside DHCP allocation. |
| 192.0.2.30 | API VIP. `api.virt-lab.example.test` and `api-int.virt-lab.example.test` resolve here. |
| 192.0.2.31 | Ingress VIP. `*.apps.virt-lab.example.test` resolves here. |
| 198.51.100.0/24 | Routed out-of-band network with iLO endpoints. Allow only required flows. |
| 10.128.0.0/14, /23 per node | OVN-Kubernetes pod allocation. |
| 172.30.0.0/16 | Kubernetes service allocation. |

## Reachability

| Initiator → listener | Transport | Why |
| --- | --- | --- |
| Bootstrap Ironic, then permanent Ironic → each iLO | TCP 443 | Authenticate to Redfish, attach virtual media, set boot override and manage power. |
| Each iLO → active virtual-media HTTP server | TCP 6183 by default for HTTPS, 6180 for HTTP where configured | iLO fetches the ISO URL it receives from Ironic. Check ACLs from the BMC subnet to the bootstrap guest and permanent service, including the control-plane/provisioner paths required by the Red Hat port matrix. Verify redirects and firmware TLS behavior. |
| Live target host/IPA ↔ provisioning services | Ironic API TCP 6385/6388 as applicable, conductor → IPA TCP 9999 and image serving as advertised | Agent callback, inspection, deployment commands and image download. Verify actual listeners and image URL for the patch. |
| First boot of physical node → internal API VIP | TCP 22623 | Machine Config Server serves role configuration at `/config/master` or `/config/worker`. Restrict to intended node networks. |
| Kubelet → internal API VIP, admin → API VIP | TCP 6443 | API registration, certificates, status and administrative API calls. |
| External clients → ingress VIP | TCP 443/80 | Application Routes. |
| Provisioner, bootstrap and nodes → site services | DNS TCP/UDP 53, NTP UDP 123, DHCP UDP 67/68, approved image endpoints TCP 443 | Identity, time, addressing, and release/RHCOS image access. DHCP may use a relay. |
| Control-plane and workers ↔ each other | Release network port matrix | Includes etcd between control-plane peers, node and OVN-Kubernetes traffic, and communication for VIP ownership. Preserve L2/ARP behavior for the VIPs and bootstrap guest MAC. |

See Red Hat’s complete network requirements, including port scope and MTU. The table above highlights this design’s dependencies. [OCP 4.20 bare-metal IPI, sections 3.2.6–3.2.8](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)

## Checklist before approval

- Verify the server, NIC, storage controller, CPU, firmware, and RHEL/RHCOS compatibility for the selected patch and the actual hardware. Confirm BMC Virtual Media privileges, licensing where applicable, supported Redfish Actions, a trusted certificate with the correct identity, and access from all executing Ironic locations. Check UEFI settings on all six hosts. HPE iLO4 on ninth-generation systems lacks supported virtual media for this flow. Validate the exact iLO generation and firmware. [OCP 4.20 hardware and BMC guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [Red Hat Ecosystem Catalog](https://catalog.redhat.com/en/hardware)
- Size the RHEL 9 provisioner, masters and workers against Red Hat’s minimums and the workload. The 4.20 IPI requirements list 4 CPUs, 16 GB RAM and 100 GB storage for bootstrap and for each control-plane node, and 2 CPUs, 8 GB and 100 GB per worker, with 300 IOPS in each row. Size the provisioner for the bootstrap guest and its own overhead. The x86_64 baseline requires x86-64-v2 instruction support. Check storage latency and throughput, especially etcd. Enable Intel VT-x or AMD-V in firmware for the provisioner and virtualization workers. Enable IOMMU when required by a device-passthrough design. [OCP 4.20 bare-metal prerequisites](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [Virtualization 4.20 requirements](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/installing)
- Record each physical NIC MAC from its hardware inventory and compare it to DHCP and the switch topology. On an existing host OS or an approved discovery console, compare `lsblk -d -o NAME,SIZE,MODEL,SERIAL,WWN` with controller inventory. Match one intended disk or controller logical volume by the serial or WWN visible to IPA. Preserve existing data separately before installation.
- Verify DHCP relay or scopes, L2 forwarding of the guest MAC, A/PTR records, wildcard resolution, and site-approved IP allocation evidence for both VIPs and the provisioning address. Use IPAM, DHCP and switch evidence to establish availability. Confirm NTP sync from the provisioner and the host network. Confirm image access from bootstrap and nodes as well as the provisioner.
- Confirm the RHEL provisioner uses system libvirt, can launch KVM guests, and attaches the `baremetal` bridge to the physical machine network. Put the provisioner IP/default route on the bridge and enslave the site uplink, such as `eno1`. Use a management console and the Red Hat NetworkManager procedure for bridge changes because activating a profile can interrupt SSH. No dedicated `provisioning` bridge is needed in this topology. [OCP 4.20 provisioner setup, sections 3.3.1–3.3.4](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)

## Configure the provisioner before preflight

On the **RHEL provisioner**, use a registered RHEL 9.x host, an installer account with the documented libvirt access, the system KVM/QEMU and libvirt packages, modular daemon sockets (or the installed supported libvirt service layout), and an active default storage pool. Follow the documented package and privilege setup for the exact RHEL release. Verify the provisioner's disk space for image extraction and the guest disk. [OCP 4.20 provisioner preparation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)

As part of that procedure, use the following from the **RHEL provisioner** to install packages and verify the account's system libvirt storage access. The package command changes the provisioner. Log in again after any group membership change.

```bash
sudo dnf install -y libvirt qemu-kvm mkisofs python3-devel jq ipmitool
virsh -c qemu:///system pool-list --all
```

The following is an example of creating the bridge profiles from the **RHEL provisioner console**. It changes local networking. Here `eno1` is the approved untagged machine-network NIC. Adapt the uplink, prefix, gateway and DNS. For an existing uplink, migrate its active NetworkManager profile to the bridge under the site change plan before activating a competing profile.

```bash
sudo nmcli connection add type bridge ifname baremetal con-name baremetal \
  ipv4.method manual ipv4.addresses 192.0.2.10/24 \
  ipv4.gateway 192.0.2.1 ipv4.dns 192.0.2.53
sudo nmcli connection add type bridge-slave ifname eno1 \
  con-name baremetal-uplink master baremetal
sudo nmcli connection up baremetal
sudo nmcli connection up baremetal-uplink
```

Check the machine network MTU of at least 1500 end to end. Resolve any VLAN, MAC forwarding, or routing issue before bootstrapping.

## Read-only provisioner checks

On the **RHEL provisioner**, install the prerequisite tools from the Red Hat setup procedure and run from the repository root as the intended installer account with system libvirt access.

```bash
bash scripts/preflight.sh baremetal virt-lab.example.test
ip route get 198.51.100.11
curl -sS -o /dev/null -w '%{http_code}\n' https://quay.io/v2/
```

The script takes the Linux bridge and cluster domain. It lists KVM and libvirt access, the bridge and its links, routes, clock tracking and DNS. A failed probe returns 1. A result with no bridge members, a bad NTP state or unexpected addresses still needs investigation. Compare output with the table. The route command only resolves a local route. A registry response such as HTTP 401 establishes DNS/TLS/registry reachability, and payload authentication is verified during installer extraction.

During an authorized live preflight, use existing BMC inventory and firewall logs to confirm both Redfish and reverse ISO paths. The ISO endpoint only becomes testable once provisioner-side provisioning services publish a URL. Record the exact timestamp and phase when collecting logs. [OCP 4.20 bare-metal validation checklist](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)
