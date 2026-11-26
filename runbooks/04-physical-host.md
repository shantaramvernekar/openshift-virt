# 4. Follow master-0 from power-off

[View the Redfish and IPA sequence.](../diagrams/README.md#redfish-and-ipa)

1. The installer translates the `master-0` entry into a `BareMetalHost` and a credential Secret in the same namespace, typically `openshift-machine-api`. The BMH contains the boot MAC, disk hint, requested online state, BMC address and `spec.bmc.credentialsName`. The latter points to the Secret containing `username` and `password`. Use the live reference to find the generated Secret name. The installer owns these initial objects.
2. The Metal³ project supplies the Bare Metal Operator (BMO), a Kubernetes controller that watches the `BareMetalHost` custom resource defined by the CRD. BMO reconciles desired state and updates observed provisioning state and errors. It asks Ironic, the provisioning service, to perform the hardware operations.
3. Ironic uses the Redfish management API exposed by HPE iLO at `198.51.100.11`, using the system path `/redfish/v1/Systems/1`. Ironic asks iLO to insert virtual media using the served ISO URL, select a one-time virtual CD/DVD boot, and power on the system. iLO initiates its own HTTP(S) connection to that URL. An authenticated Redfish connection proves only that first network leg.
4. The physical server boots the live ISO, brings up the boot NIC `02:00:00:00:00:01` with lease `192.0.2.41`, and starts IPA. Ironic and IPA exchange inventory, inspection and deployment instructions. In 4.20, use Ironic and ramdisk logs for inspection. The separate Ironic Inspector component in older releases applies through 4.16.
5. IPA uses `coreos-installer` on the target to write RHCOS to the disk matching `LAB-master-0-OS`. Ironic coordinates the transition to local disk boot. Firmware can perform additional reboots during inspection, cleaning, deployment or retry. Treat live-media boot and first installed-disk boot as the two conceptual phases.
6. The installed host runs Ignition at first boot. Its role stub retrieves control-plane configuration from `https://api-int.virt-lab.example.test:22623/config/master`. The worker path is `/config/worker`. MCS serves these documents. Kubelet separately connects to the Kubernetes API on TCP 6443 and control-plane services start from the configuration rendered for the node.

[OCP 4.20 bare-metal installation overview, boot modes and BMC syntax](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [OCP 4.20 BareMetalHost fields and adding hosts](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/bare-metal-post-installation-configuration)

## Object boundaries

| Object | What it represents | Ownership in this walkthrough |
| --- | --- | --- |
| `BareMetalHost` and its Secret | Hardware desired state and provisioning status. Typical phase values include `registering`, `inspecting`, `available`, `provisioning`, and `provisioned`. Cleaning and retries can introduce other transitions. | Initial objects from installer. After install, admins supply a same-namespace BMH and credential Secret when enrolling new raw hosts. BMO reconciles BMHs. |
| `Machine` | Machine API request/provider representation of a node, associated with a physical host in IPI. A provider can claim an eligible BMH. `status.nodeRef` ties it to the registered Node. | Initial control-plane Machines are installer-generated. Workers are created from the installer-generated MachineSet by controllers. |
| `MachineSet` | Maintains desired number of matching Machines. | Installer seeds the worker MachineSet. Admins manage worker MachineSet capacity after install. |
| `Node` | Registered Kubernetes OS/kubelet identity with health and scheduling state. | Kubelet registers; controllers report conditions. |

Ignition handles first-boot machine initialization. The Machine Config Operator then reconciles rendered node configuration, OS/configuration transitions and pool status. On the **cluster CLI**, read the BMH and referenced Secret's name only. On an authorized **physical-host console**, examine Ignition and kubelet journals if boot fails.

```bash
oc -n openshift-machine-api describe bmh master-0
oc -n openshift-machine-api get bmh master-0 -o jsonpath='{.spec.bmc.credentialsName}{"\n"}'
oc -n openshift-machine-api get machines -o wide
```

A `provisioned` host can still be missing from the Kubernetes API. Treat that as a handoff to first-boot, DNS, MCS, API or kubelet diagnosis. [OCP 4.20 Machine API overview](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/machine_management/overview-of-machine-management), [OCP 4.20 MachineConfig overview](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/machine_configuration/index)
