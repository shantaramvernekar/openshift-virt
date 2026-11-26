# 7. Disconnected registry and image cache

Keep [the connected configuration](02-installer-config.md) as the baseline. For a disconnected deployment, add a registry mirror and ensure the bootstrap guest, provisioner, and installed nodes can resolve, reach and trust it.

1. From an approved **mirror workstation**, mirror the selected x86_64 4.20 release and release content to a local registry with the 4.20 mirroring procedure. Include the release digest and referenced components. Prepare registry authentication and the PEM CA chain. In a fully isolated site use the supported mirror-to-disk/import workflow. [OCP 4.20 bare-metal disconnected procedure, section 3.3.16](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [OCP 4.20 disconnected environments](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/disconnected_environments/index)
2. Put mirror auth in the private pull secret. In the private install config, add `additionalTrustBundle` when a private CA is required, and insert the release digest mirror rules generated for this mirror as `imageDigestSources`. The 4.20 bare-metal mirroring chapter also shows the legacy `imageContentSources` key emitted by `oc adm release mirror`. Use the installer schema for the selected patch and supply one representation. Verify the installer host's own registry trust separately. [OCP 4.20 install parameters](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure), [Installer release-4.20 InstallConfig type](https://github.com/openshift/installer/blob/release-4.20/pkg/types/installconfig.go)
3. Extract the matching bare-metal installer from the **mirrored payload** on the **RHEL provisioner**, using the Linux `oc` binary, registry trust and private mirror credentials.

   ```bash
   oc adm release extract --registry-config "$HOME/ocp-private/pull-secret.json" \
     --command=openshift-baremetal-install "$MIRRORED_RELEASE"
   ./openshift-baremetal-install version
   ```

4. Mirror the **QEMU bootstrap disk** separately as an HTTPS/HTTP artifact if the default stream endpoint is unreachable. On a **connected staging workstation** running the matched Linux installer, obtain the URL and uncompressed checksum below. Download the compressed QEMU disk, verify the stream checksum, and serve the file from a reachable internal web cache with site-approved TLS. Set `platform.baremetal.bootstrapOSImage` in the private template to the resulting URL, for example `https://cache.example.test/rhcos/<qemu-file>?sha256=<uncompressed-sha256>`. Restrict loopback or network access per site. This cache also works as a connected-install bandwidth optimization.

   ```bash
   openshift-baremetal-install coreos print-stream-json |
     jq -er '.architectures.x86_64.artifacts.qemu.formats["qcow2.gz"].disk |
       [.location, .sha256, .["uncompressed-sha256"]] | @tsv'
   ```

   The RHCOS metal disk source is already represented in the mirrored release. The per-host media ISO still needs to be served to each BMC at deployment time and its advertised URL must be reachable. Review the [artifact table](03-bootstrap.md#three-separate-artifacts) and confirm the payload component availability and any supported overrides for the chosen patch. [OCP 4.20 RHCOS cache and media ports](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/installing_on_bare_metal/installer-provisioned-infrastructure)
5. Mirror the compatible OpenShift Virtualization catalog, Operator bundles and related images separately, and serve approved guest images from an internal CDI-reachable source. Use the resulting CatalogSource and mirror policies in the virtualization stage. Confirm that the base cluster, Operators and VM smoke images can pull using the intended disconnected DNS and trust path. [OCP 4.20 Operator mirroring](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/disconnected_environments/index), [OpenShift Virtualization 4.20 installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/virtualization/installing)
