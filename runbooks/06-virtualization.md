# 6. Enable OpenShift Virtualization

Start after [base-cluster acceptance](05-acceptance.md). OCP 4.20 pairs with OpenShift Virtualization 4.20. Confirm the selected patch’s prerequisites, known issues and tested combinations for the server, CPU, guest OS, NIC and CSI driver. Use the published Red Hat catalog for the supported channel, and verify the installed CSV version before applying the operand. [OpenShift Virtualization 4.20 requirements and installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/installing)

## Verify worker and storage readiness

- On `worker-0`, `worker-1` and `worker-2`, verify VT-x/AMD-V in firmware and check `/dev/kvm`. From the **cluster CLI**, an authorized admin can use `oc debug node/<actual-worker-name> -- chroot /host ls -l /dev/kvm`, which creates a temporary debugging pod. Later check the specific node allocatable resource `devices.kubevirt.io/kvm` and `virt-handler` readiness. Compare CPU models, flags, firmware and guest placement constraints across workers.
- Size against one unavailable worker. Sum allocatable resources on the two smallest surviving workers, subtract cluster and virtualization overhead and other workloads, and test each VM's actual placement, anti-affinity, CPU feature and storage topology constraints. For example, three workers each with 48 GiB available after reservations give an N−1 upper bound of 96 GiB before migration headroom. A VM still needs a single fitting worker. A live migration temporarily needs resources on both source and target. Host failure recovery is a separate exercise because live migration needs a functioning source.
- Select an OCP-supported CSI driver and a supported backend and version. Check `StorageClass` topology, binding, expansion, snapshots, reclaim policy and recovery. Confirm CSI supports the requested combination. `ReadWriteOnce` allows writable mounting on one node and can suit a single-host boot test. `ReadWriteMany` permits simultaneous writable access from multiple nodes and is needed for this shared-PVC migration example. `Block` exposes a raw device. `Filesystem` stores a disk image in a mounted filesystem. The example explicitly requests RWX Block. A suitable driver may use RWX Filesystem with an appropriate VM configuration.
- After CDI is ready, inspect `oc get storageclass` and `oc get storageprofile <storage-class> -o yaml`. Check the StorageProfile's `status.claimPropertySets` for supported defaults. If the driver has no recognized profile, supply settings explicitly and confirm they are correct. Ensure importer pods can reach the approved guest image and trust its CA. For a site requiring authenticated image import, configure CDI's source credential reference separately. Allow enough PVC space for the image's expanded size.
- Use pod-network masquerade for the smoke VM, with DHCP inside the guest. A Kubernetes Service supplies stable reachability. Plan additional networks, VLANs, guest IP allocation, routing and policy with the network team. [Optional NMState and NAD examples](../examples/virtualization/optional-network/README.md) are separate from the baseline.

[OpenShift Virtualization 4.20 storage](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/storage), [Networking](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/networking), [Live migration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/live-migration)

## Install the Operator and operand

From the repository root on the **cluster CLI** as cluster administrator, inspect the connected catalog. Confirm the `stable` channel and a compatible 4.20 CSV. If there is already an OperatorGroup in `openshift-cnv`, inspect it and reuse it when compatible. OLM requires one compatible OperatorGroup in the namespace.

```bash
oc -n openshift-marketplace get catalogsource redhat-operators
oc -n openshift-marketplace get packagemanifest kubevirt-hyperconverged -o json |
  jq -r '.status | .catalogSource, (.channels[] | [.name, .currentCSV] | @tsv)'
oc get operatorgroup -n openshift-cnv
```

The next commands mutate the cluster. When there is an existing OperatorGroup, apply only the required Namespace and Subscription documents from [00-operator.yaml](../examples/virtualization/00-operator.yaml). The connected example lets OLM resolve the current CSV from the compatible channel and uses automatic InstallPlan approval. Add a reviewed `startingCSV` for a planned initial version when the catalog contains it. In a change-controlled environment, use manual approval and review the InstallPlan before approving it. If the catalog is mirrored, use its actual source and compatible channel.

```bash
oc apply -f examples/virtualization/00-operator.yaml
oc -n openshift-cnv get subscription,installplan,csv
```

Wait until the installed OpenShift Virtualization CSV is the intended 4.20 version and its phase is `Succeeded`. Then apply [10-hyperconverged.yaml](../examples/virtualization/10-hyperconverged.yaml) and check the operand.

```bash
oc apply -f examples/virtualization/10-hyperconverged.yaml
oc -n openshift-cnv wait hco/kubevirt-hyperconverged --for=condition=Available --timeout=15m
oc -n openshift-cnv get hco kubevirt-hyperconverged -o json |
  jq '.status | {conditions, versions}'
oc -n openshift-cnv get pods -o wide
oc get nodes -l node-role.kubernetes.io/worker -o json |
  jq -r '.items[] | [.metadata.name, .status.allocatable["devices.kubevirt.io/kvm"]] | @tsv'
```

Require HCO `Available=True`, no degradation or ongoing rollout, ready pods/daemonsets on eligible workers, and a nonzero KVM count on each. [Virtualization 4.20 CLI install and verification](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/installing)

## Boot, connect and prove persistence

Create reviewed copies of [30-vm.yaml](../examples/virtualization/30-vm.yaml) and [40-service-route.yaml](../examples/virtualization/40-service-route.yaml). Replace the image URL, storage class, public SSH key and Route hostname for your site. Use a supported x86_64 Linux cloud image with cloud-init, Python 3 at `/usr/bin/python3`, systemd, SSH and a DHCP client. The guest HTTP endpoint is a smoke test. Limit the Route to an approved test audience.

On the **cluster CLI**, set `VM_MANIFEST` and `VM_ROUTE_MANIFEST` to the reviewed copies, then create the workload and wait for it to become ready.

```bash
oc apply -f examples/virtualization/20-namespace.yaml
oc apply -f "$VM_MANIFEST"
oc apply -f "$VM_ROUTE_MANIFEST"
oc -n virt-smoke wait vmi/virt-smoke --for=create --timeout=15m
oc -n virt-smoke wait vmi/virt-smoke --for=condition=Ready --timeout=15m
oc -n virt-smoke get dv,pvc,vm,vmi,pod,svc,route -o wide
```

Look for `DataVolume=Succeeded`, a bound PVC, and a ready VMI on a worker. On the **admin workstation** with matching `virtctl`, trusted router CA, and the SSH key, test the guest via the API-backed SSH tunnel. Set `GUEST_ROUTE` to the reviewed Route hostname. Retry SSH and HTTP until cloud-init has converged.

```bash
virtctl -n virt-smoke ssh lab@vm/virt-smoke -i "$HOME/.ssh/id_ed25519"
curl -fsS "https://$GUEST_ROUTE/health"
```

The route should return `guest-ok`. In the **guest SSH session**, inspect its address and gateway, verify DNS for the ingress host using `getent ahostsv4 virt-smoke.apps.virt-lab.example.test` with the site name, and write a marker on the root disk.

```bash
cloud-init status --wait
ip -4 addr show
ip route
printf '%s\n' "$(date -u +%FT%TZ)" | sudo tee /var/lib/virt-smoke/persistence
sudo chmod 0644 /var/lib/virt-smoke/persistence
```

From the **admin workstation**, record the marker over the Route. From the **cluster CLI**, restart the VM. Poll after the restart until the new VMI is Ready, and compare its UID to the original. Then run the final comparison from the **admin workstation** in the shell retaining `marker`.

```bash
# Admin workstation
marker=$(curl -fsS "https://$GUEST_ROUTE/persistence")
test -n "$marker" || exit 1
# Cluster CLI
oc -n virt-smoke get vmi virt-smoke -o jsonpath='{.metadata.uid}{"\n"}'
virtctl -n virt-smoke restart virt-smoke
oc -n virt-smoke get vmi virt-smoke -w
# Admin workstation, after observing a different UID and Ready
test "$(curl -fsS "https://$GUEST_ROUTE/persistence")" = "$marker"
```

[OpenShift Virtualization 4.20 VM creation and access, chapter 9](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/virtualization/index)

## Prove live migration on an eligible VM

Confirm shared storage on both nodes, compatible CPUs and schedulable resources, a migratable interface, and routable migration traffic between virt-launcher pods. Check live migration port and policy requirements for the actual configuration, including reserved TCP 49152 and 49153, relevant MTU, and sufficient bandwidth. Review host devices such as passthrough NICs or GPUs and provider support before assuming they can migrate. Pod-network bridge binding can block live migration. The baseline uses masquerade on the pod network and avoids device passthrough. [Virtualization 4.20 migration requirements](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/live-migration)

Start this loop in a separate **admin workstation** terminal before migration. Stop it afterward and retain the results, including any failed requests.

```bash
while true; do
  date -u +%FT%TZ
  curl -fsS --max-time 3 "https://$GUEST_ROUTE/health" || echo "guest probe failed"
  sleep 2
done
```

On the **cluster CLI**, record the source, require the `LiveMigratable` condition, create the migration, and check phase, source, destination and failure state.

```bash
source_node=$(oc -n virt-smoke get vmi virt-smoke -o jsonpath='{.status.nodeName}')
test -n "$source_node" || exit 1
oc -n virt-smoke wait vmi/virt-smoke --for=condition=LiveMigratable --timeout=30s || exit 1
migration=$(oc create -f examples/virtualization/50-migration.yaml -o name) || exit 1
oc -n virt-smoke wait "$migration" --for=jsonpath='{.status.phase}'=Succeeded --timeout=15m
oc -n virt-smoke get "$migration" -o wide
oc -n virt-smoke get vmi virt-smoke -o json | jq '.status | {nodeName, migrationState}'
destination_node=$(oc -n virt-smoke get vmi virt-smoke -o jsonpath='{.status.nodeName}')
test -n "$destination_node" && test "$source_node" != "$destination_node"
```

Require `Succeeded`, `migrationState.completed=true`, no failed flag, matching source/target node evidence and the VMI resident on the target. Check external guest health and marker again, and record any interruptions during the window. [Virtualization 4.20 migration monitoring](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/live-migration)
