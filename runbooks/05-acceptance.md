# 5. Handoff, worker-0, and cluster acceptance

[View the handoff diagram.](../diagrams/README.md#bootstrap-handoff)

The control-plane nodes bring up permanent etcd and API services while the bootstrap VM is running. Keepalived gives the bootstrap API VIP higher priority during bootstrap. After bootstrap completes, the installer on the provisioner tears down the libvirt guest. A control-plane node takes over 192.0.2.30 and its HAProxy serves the API endpoint. The permanent control plane takes over Machine Config Server traffic as well. The Cluster Version Operator rolls out the Cluster Bare Metal Operator, which runs BMO and Ironic on the permanent control plane, with the service address 192.0.2.21. The bootstrap script stops its Ironic/BMO services after the control-plane hosts are provisioned and releases the host reconciliation pause. API VIP failover, permanent Operator rollout, worker Machine creation and the start of worker provisioning can overlap around teardown. The ingress VIP at 192.0.2.31 is associated with the router placement. Check the actual owner and router pods as the cluster converges. [OCP 4.20 bare-metal IPI architecture and deployment](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [4.20 bootstrap provisioning handoff](https://github.com/openshift/installer/blob/release-4.20/data/data/bootstrap/baremetal/files/usr/local/bin/master-bmh-update.sh), [Cluster Bare Metal Operator 4.20 responsibilities](https://github.com/openshift/cluster-baremetal-operator/tree/release-4.20)

For **worker-0**, the worker MachineSet supplies a Machine and the bare-metal provider claims an available host. Read the actual consumer reference to establish the pairing. In-cluster Ironic talks to iLO at 198.51.100.14, iLO fetches the media from the active service, then IPA probes the hardware and installs to `LAB-worker-0-OS`. The first installed boot at 192.0.2.44 applies `/config/worker` from the permanent MCS. Kubelet registers through 6443, its node reference appears on the Machine, and the node reaches `Ready` when kubelet, CRI and networking are healthy.

## Inspect and accept the base cluster

On the **RHEL provisioner**, observe the installer state. Use the same installation directory as `create cluster`.

```bash
openshift-baremetal-install --dir "$INSTALL_DIR" wait-for bootstrap-complete
openshift-baremetal-install --dir "$INSTALL_DIR" wait-for install-complete
```

On the **cluster CLI**, use the protected kubeconfig at `$INSTALL_DIR/auth/kubeconfig` on the provisioner, or an approved workstation credential. The following commands are read-only.

```bash
oc get clusterversion
oc -n openshift-machine-api get bmh,machine,machineset -o wide
oc -n openshift-machine-api get bmh worker-0 \
  -o jsonpath='{.spec.consumerRef.name}{"\n"}{.status.provisioning.state}{"\n"}'
oc get nodes -o wide
oc get co
oc get mcp
oc -n openshift-ingress get pods -o wide
oc -n openshift-machine-api get pods -o wide
```

| Check | Acceptance signal |
| --- | --- |
| Installer | Boots and install finish, and the temporary libvirt domain is removed. |
| BMH and Machine | Six expected hardware objects are healthy and provisioned. Worker Machines are running with the expected node references and the worker MachineSet meets its replica target. |
| Nodes | Three control-plane nodes and three workers are `Ready`. Match the six InternalIPs to inventory. Node names follow site hostname configuration. |
| Version and Operators | Expected 4.20.z version. ClusterVersion available and settled. Operators show `Available=True`, `Progressing=False`, `Degraded=False` once converged. Investigate deviations. |
| MachineConfigPools | Master and worker pools show updated, neither updating nor degraded, with desired machines ready. |
| Ingress | Router pods are ready. A known application Route returns its expected response from outside the cluster through the ingress VIP with valid TLS. |

For a real application Route, discover it from the **cluster CLI**, then test from an **external admin workstation** through ordinary wildcard DNS, with the router CA trusted.

```bash
# Cluster CLI. Set APP_NAMESPACE for the existing app.
oc -n "$APP_NAMESPACE" get route,svc,endpointslices
# External admin workstation. Set ROUTE_HOST and EXPECTED_BODY for the existing app.
dig +short "$ROUTE_HOST"
test "$(curl -fsS --max-time 10 "https://$ROUTE_HOST/health")" = "$EXPECTED_BODY"
```

If the cluster has no application yet, an authorized operator can instantiate [the acceptance example](../examples/acceptance-route.yaml). On the **cluster CLI**, replace the web image placeholder in a reviewed copy and apply it with `oc apply -f "$ACCEPTANCE_MANIFEST"`, using the path of that copy. The example serves `openshift-ipi-ok` at `/health`. Then run the external test with `ROUTE_HOST=ipi-smoke.apps.virt-lab.example.test` and `EXPECTED_BODY=openshift-ipi-ok`. Keep the application, service endpoints, route admission, wildcard DNS, router/TLS, and external response as separately observable signals.

[OCP 4.20 validation and troubleshooting](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [Ingress and load balancing](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ingress_and_load_balancing/index)
