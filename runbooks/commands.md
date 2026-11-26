# Command cheat sheet

Run checks in the indicated environment with the intended credentials and site values. Commands that make changes live in the referenced runbooks.

| Run from | Command | Look for |
| --- | --- | --- |
| RHEL provisioner | `bash scripts/preflight.sh baremetal virt-lab.example.test` | KVM, libvirt, expected bridge and DNS, synchronized time |
| Admin workstation | `dig +short api.virt-lab.example.test` | API VIP 192.0.2.30 |
| Admin workstation | `dig +short probe.apps.virt-lab.example.test` | Ingress VIP 192.0.2.31 |
| RHEL provisioner | `openshift-baremetal-install version` | Approved patch and payload |
| RHEL provisioner | `openshift-baremetal-install coreos print-stream-json` | x86_64 QEMU image stream artifact |
| RHEL provisioner | `virsh -c qemu:///system list --all` | Bootstrap domain before handoff |
| RHEL provisioner | `virsh -c qemu:///system domiflist "$BOOTSTRAP_DOMAIN"` | External NIC on `baremetal` |
| RHEL provisioner | `virsh -c qemu:///system domblklist "$BOOTSTRAP_DOMAIN" --details` | Attached boot disk |
| RHEL provisioner | `tail -n 100 "$INSTALL_DIR/.openshift_install.log"` | Current installer asset or milestone |
| RHEL provisioner | `openshift-baremetal-install --dir "$INSTALL_DIR" wait-for bootstrap-complete` | Permanent control plane handoff milestone |
| RHEL provisioner | `openshift-baremetal-install --dir "$INSTALL_DIR" wait-for install-complete` | Installer completion milestone |
| Bootstrap VM | `sudo journalctl -b -u bootkube.service -u release-image.service` | Release pull and bootstrap control-plane activity |
| Bootstrap VM | `sudo podman ps -a` and `sudo crictl ps -a` | Discover provisioning and control-plane containers |
| Cluster CLI | `oc -n openshift-machine-api get bmh,machines,machinesets` | Hardware state, worker provider state and desired replicas |
| Cluster CLI | `oc -n openshift-machine-api describe bmh master-0` | Last reconciliation event and provisioning stage |
| Cluster CLI | `oc get nodes -o wide` and `oc get co` and `oc get mcp` | Nodes, Operators, rendered config rollout |
| Cluster CLI | `oc get csr` | Pending or approved kubelet certificates, for debugging |
| Cluster CLI | `oc -n openshift-ingress get pods -o wide` | Router readiness and placement |
| Admin workstation | `curl -fsS "https://$ROUTE_HOST/health"` | Known end-to-end health response |
| Cluster CLI | `oc -n openshift-cnv get subscription,installplan,csv,hco` | Operator installation and operand status. Query HCO after CRD installation. |
| Cluster CLI | `oc get storageclass,storageprofile` | Supported driver and CDI storage properties |
| Cluster CLI | `oc -n virt-smoke get dv,pvc,vm,vmi,vmim -o wide` | Guest import, placement and migration status |
| Admin workstation | `virtctl -n virt-smoke ssh lab@vm/virt-smoke -i "$HOME/.ssh/id_ed25519"` | SSH access to the cloud-init account |
