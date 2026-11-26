# Source review and local validation

## Reference review

The reference diagrams informed the installation sequence. The [overall IPI flow](../docs/Bare-metal%20OpenShift%20IPI%20provisioning%20flow.png), [bootstrap VM](../docs/How%20the%20OpenShift%20bootstrap%20VM%20starts.png), [HPE iLO](../docs/How%20Ironic%20boots%20an%20HPE%20server.png), [physical host](../docs/Bare-metal%20server%20to%20OpenShift%20node.png), [handoff](../docs/From%20bootstrap%20VM%20to%20permanent%20control%20plane.png), and [worker acceptance](../docs/Provision%20workers%2C%20verify%20the%20cluster.png) are preserved as supplied. The [Ignition diagram](../docs/OpenShift%20installation%20with%20Ignition.png) illustrates UPI. Its role-fetch and kubelet stages also inform the IPI walkthrough.

| Reference topic | OpenShift 4.20 treatment |
| --- | --- |
| Several installation methods and address plans | One DHCP-based IPI inventory with a fixed bootstrap guest MAC, a permanent provisioning address and cluster-managed VIPs. The static bootstrap variation uses the three `bootstrapExternalStatic*` fields. |
| Ironic Inspector and 5050/5051 | The IPI workflow describes the standalone Inspector component through 4.16. Use 4.20 Ironic/IPA logs to diagnose inspection. The generic Red Hat port table still lists Inspector ports. |
| Dell virtual media endpoint | The Dell virtual-media endpoint uses `idrac-virtualmedia://.../Systems/System.Embedded.1`. The HPE example uses `redfish-virtualmedia://.../Systems/1`, with actual system IDs confirmed on the selected hardware. |
| Virtual media arrow and ISO/image terminology | Show both HTTPS Redfish and the BMC-initiated media GET. Distinguish the RHCOS QEMU artifact, per-host live media and RHCOS metal disk image. The default provisioning payload supplies the latter two sets of inputs. |
| UPI bootstrap teardown | In this IPI design the installer removes its temporary libvirt guest and the cluster assumes VIP ownership. The UPI diagram's manual load-balancer detachment applies to its UPI walkthrough. |
| CLI Operator subscription | Use `openshift-cnv`, including its monitoring label, the `stable` channel, a compatible 4.20 CSV and the HCO CR after the CSV succeeds. |
| VM HA and shared storage | Size for the loss of one worker, plan restart/recovery separately from live migration, and verify the exact driver supports the requested RWX/Block PVC. |

[Red Hat 4.20 bare-metal IPI](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [Red Hat 4.20 Virtualization](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/virtualization/index)

## Reproduce the local checks

On an **admin workstation** with Python 3, PyYAML, OpenSSH `ssh-keygen`, and Bash, run from the repository root.

```bash
python3 scripts/validate-examples.py
```

This script renders a temporary InstallConfig with a throwaway SSH key and dummy credentials, tests private permissions, checks that a rerun preserves the first output, and checks that loosely permissioned inputs are rejected. It parses the YAML resource documents, nested guest cloud-init and CNI JSON, checks the host and network inventory across files, and validates Bash syntax and relative documentation links. It returns nonzero at the failing check. The [preflight script](../scripts/preflight.sh) runs on RHEL and is covered locally by syntax validation.

## Live verification still required

Run the release-matched installer on the approved RHEL provisioner after validating target firmware, inventory and hardware, reverse ISO routing, Ironic and IPA exchange, DHCP/first boot, and VIP ownership. Confirm the patch's payload and OLM channel, then execute the base and virtualization acceptance tests with the site's network, registry, CSI driver and approved guest image. Server-side admission, guest boot and persistence, and observed migration/recovery behavior need the live environment.

## Recorded local result

- The dummy render succeeded with punctuation in the credentials and a generated SSH key. The directory and file modes were 0700 and 0600. The renderer rejected broad input permissions and a reused directory without exposing the test credentials. The dummy key also parsed in the VM's rendered cloud-init.
- All 15 manifest documents parsed as YAML, including the nested cloud-init and CNI configuration in their respective formats. Inventory checks covered six BMC/host/disk mappings, network ranges, VIPs, and the topology and preflight documentation. The preflight script and 24 Bash blocks passed syntax validation. All 38 local Markdown links resolved. Git ignore checks matched nine dummy sensitive paths.
- Schema checks passed for the rendered DHCP InstallConfig, static-bootstrap variation, Dell BMC variation, and all 15 resource documents across 11 kinds. The checks used the 4.20 installer, Route, OLM and NMState schemas, Kubernetes 1.33 core/apps OpenAPI, the HCO 1.17 CRD and KubeVirt 1.7.4 schema referenced by that HCO branch, and the upstream NAD CRD. [Installer schema](https://github.com/openshift/installer/blob/release-4.20/data/data/install.openshift.io_installconfigs.yaml), [OpenShift API](https://github.com/openshift/api/blob/release-4.20/openapi/openapi.json), [Kubernetes OpenAPI](https://github.com/kubernetes/kubernetes/tree/v1.33.0/api/openapi-spec/v3), [OLM CRDs](https://github.com/openshift/operator-framework-olm/tree/release-4.20/vendor/github.com/operator-framework/api/crds), [NMState CRD](https://github.com/openshift/kubernetes-nmstate/blob/release-4.20/deploy/crds/nmstate.io_nodenetworkconfigurationpolicies.yaml), [HCO CRD](https://github.com/kubevirt/hyperconverged-cluster-operator/blob/release-1.17/config/crd/bases/hco.kubevirt.io_hyperconvergeds.yaml), [KubeVirt OpenAPI](https://github.com/kubevirt/kubevirt/blob/v1.7.4/api/openapi-spec/swagger.json), [NAD CRD](https://github.com/k8snetworkplumbingwg/network-attachment-definition-client/blob/master/artifacts/networks-crd.yaml)
- Reviewed release extraction and defaults, DHCP/static bootstrapping, BMC conventions, image sources, ports, cluster handoff, Operator install order, VM storage and live-migration prerequisites against the sources linked in each runbook. These checks use published schemas and source code. Confirm installer validation, site policy and admission/defaulting with your exact patch and connected hardware.
