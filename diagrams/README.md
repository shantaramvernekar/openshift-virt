# Editable Mermaid diagrams

Edit the Mermaid blocks directly in this file. The addresses match the [inventory](../config/inventory.yaml). Arrows show the request initiator, information flow, or action named on the connection.

## Topology

```mermaid
flowchart LR
    admin["Admin workstation and external application clients"]
    registry["Release registry and RHCOS artifact store"]
    site["Site DHCP, DNS 192.0.2.53 and NTP 192.0.2.54"]
    subgraph machine["Machine network · 192.0.2.0/24"]
        subgraph provisioner["RHEL provisioner · 192.0.2.10"]
            installer["4.20 installer and KVM/libvirt"]
            bridge["Linux bridge baremetal"]
            bootstrap["RHCOS bootstrap guest · 192.0.2.20"]
            installer -->|creates temporary guest| bootstrap
            bootstrap ---|guest NIC uses bridge| bridge
        end
        masters["master-0 .41 · master-1 .42 · master-2 .43"]
        workers["worker-0 .44 · worker-1 .45 · worker-2 .46"]
        metal["Permanent provisioning service · 192.0.2.21"]
        api["API VIP · 192.0.2.30 · api and api-int"]
        ingress["Ingress VIP · 192.0.2.31 · *.apps"]
        bootstrap -->|owns API VIP during bootstrap| api
        masters -->|keepalived takes over API VIP| api
        masters -->|run permanent Metal³| metal
        workers -->|Ignition 22623 and kubelet 6443| api
        masters -->|Ignition 22623 and kubelet 6443| api
        ingress -->|80/443 reaches router pods| workers
    end
    bmc["BMC network · 198.51.100.0/24<br/>iLO .11/.12/.13 for masters<br/>iLO .14/.15/.16 for workers"]
    admin -->|Kubernetes API TCP 6443| api
    admin -->|application HTTPS| ingress
    installer -->|fetch release and QEMU artifact| registry
    bootstrap -->|fetch payload images| registry
    masters -->|fetch payload images| registry
    workers -->|fetch payload images| registry
    bootstrap -->|site DHCP, DNS, NTP| site
    masters -->|site DHCP, DNS, NTP| site
    workers -->|site DHCP, DNS, NTP| site
    bootstrap -->|Ironic Redfish HTTPS 443| bmc
    metal -->|Ironic Redfish HTTPS 443| bmc
    bmc -->|ISO GET TCP 6183 or 6180 during bootstrap| bootstrap
    bmc -->|ISO GET TCP 6183 or 6180 after handoff| metal
```

## Bootstrap VM

```mermaid
flowchart LR
    subgraph rhel["RHEL provisioner · 192.0.2.10"]
        config["Private install-config.yaml"]
        cli["openshift-baremetal-install create cluster"]
        manifests["Generated manifests"]
        assets["Bootstrap and role Ignition assets"]
        libvirt["System libvirt with KVM/QEMU"]
        config -->|install inputs| cli
        cli -->|generates| manifests
        manifests -->|rendered into| assets
        cli -->|starts guest over baremetal bridge| libvirt
    end
    stream["4.20 RHCOS stream QEMU disk"]
    subgraph vm["RHCOS bootstrap VM · 192.0.2.20"]
        rc["Guest boots RHCOS and applies bootstrap Ignition"]
        api["Temporary control plane"]
        mcs["Machine Config Server"]
        bmo["Bootstrap Bare Metal Operator"]
        ironic["Ironic and provisioning HTTP server"]
        rc -->|starts| api
        rc -->|starts| mcs
        rc -->|starts| bmo
        bmo -->|requests hardware operations| ironic
    end
    stream -->|disk image consumed by installer/libvirt| libvirt
    assets -->|bootstrap Ignition| rc
    libvirt -->|boots VM disk| rc
    mcs -->|serves role configs on TCP 22623| host["Installed physical nodes"]
```

## Redfish and IPA

```mermaid
sequenceDiagram
    participant API as Bootstrap Kubernetes API
    participant BMO as BMO in bootstrap VM
    participant IR as Ironic in bootstrap VM
    participant ISO as HTTP server in bootstrap VM .20
    participant BMC as master-0 iLO 198.51.100.11
    participant HOST as master-0 physical host 192.0.2.41
    participant MCS as MCS via api-int VIP .30
    participant KAPI as Kubernetes API via api-int VIP .30
    API->>BMO: BMH desired state and credential Secret reference
    BMO->>IR: Validate hardware and request provisioning
    IR->>BMC: Redfish HTTPS 443, insert ISO URL
    BMC->>ISO: GET virtual media on TCP 6183 or 6180
    ISO-->>BMC: Serve prepared boot ISO
    IR->>BMC: Set one-time virtual CD/DVD boot and power on
    BMC->>HOST: Present virtual optical drive and boot
    HOST->>IR: IPA callback and inventory
    IR->>HOST: Request deployment to the matching root disk
    HOST->>ISO: IPA downloads RHCOS installation image
    HOST->>HOST: IPA writes LAB-master-0-OS and host boots from disk
    HOST->>MCS: Ignition GET /config/master on TCP 22623
    HOST->>KAPI: Kubelet connects on TCP 6443 and registers
```

## Bootstrap handoff

```mermaid
flowchart TD
    boot["RHCOS bootstrap VM .20 owns API VIP .30"]
    cp["Physical master-0 .41, master-1 .42, master-2 .43"]
    installer["Installer on RHEL provisioner"]
    vip["Keepalived and HAProxy on permanent control plane"]
    cbo["Cluster Bare Metal Operator and Metal³ on control plane · service .21"]
    machine["Worker MachineSet and Machines in permanent API"]
    worker["worker-0 .44 · iLO 198.51.100.14"]
    ingress["Ingress VIP .31 and router pods"]
    boot -->|runs temporary API, MCS and provisioning| cp
    cp -->|etcd and API ready for handoff| installer
    installer -->|tears down bootstrap domain| boot
    boot -->|releases API VIP after bootstrap stops| vip
    cp -->|CVO starts permanent Operators| cbo
    cp -->|controllers start reconciling| machine
    machine -->|provider claims worker BMH| cbo
    cbo -->|Ironic provisions worker| worker
    worker -->|connects to permanent MCS and API| vip
    worker -->|Ready workers host router pods| ingress
```

## Virtualization enablement

```mermaid
flowchart LR
    admin["Cluster admin · workstation"]
    accepted["Accepted OCP 4.20 base cluster"]
    olm["OLM in cluster · openshift-cnv subscription"]
    hco["HyperConverged Operator · openshift-cnv"]
    components["KubeVirt, CDI and supporting operands"]
    storage["CSI backend and PVC on eligible workers"]
    vm["Guest in virt-launcher on worker-0 .44"]
    target["Eligible worker-1 .45 or worker-2 .46"]
    route["Service and Route · virt-smoke namespace"]
    accepted -->|base platform gate| admin
    admin -->|apply Namespace, OperatorGroup, Subscription| olm
    olm -->|resolves 4.20 Operator CSV| hco
    admin -->|after CSV succeeds, apply HyperConverged CR| hco
    hco -->|reconciles| components
    components -->|CDI imports guest disk| storage
    components -->|KubeVirt schedules and starts| vm
    storage -->|provides persistent root disk| vm
    vm -->|eligible live migration with shared storage| target
    route -->|stable client endpoint forwards to guest| vm
    route -->|after migration forwards to guest| target
```

The stage breakdown and diagrams use the supplied reference material. See [source corrections](../runbooks/validation.md#reference-review) for details.
