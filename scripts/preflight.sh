#!/usr/bin/env bash
# Run on the RHEL provisioner. All probes are local except DNS lookups.
set -u

if (( $# > 2 )); then
  echo 'Usage: bash scripts/preflight.sh [bridge] [cluster-domain]' >&2
  exit 2
fi
bridge=${1:-baremetal}
domain=${2:-virt-lab.example.test}
failures=0

check() {
  local label=$1
  shift
  printf '\n[%s]\n' "$label"
  if ! "$@"; then
    printf 'Check failed: %s\n' "$label" >&2
    failures=$((failures + 1))
  fi
}

check 'Provisioner CPU and KVM' grep -m 1 -oE '(^| )(vmx|svm)( |$)' /proc/cpuinfo
check 'Provisioner KVM device' ls -l /dev/kvm
check 'System libvirt access for current user' virsh -c qemu:///system list --all
check 'Linux bridge type' test -d "/sys/class/net/$bridge/bridge"
check 'Linux bridge link' ip -d link show dev "$bridge"
check 'Bridge member links' bridge link show master "$bridge"
check 'Bridge IPv4 address' ip -4 addr show dev "$bridge"
check 'Provisioner routes' ip route
check 'NTP tracking' chronyc tracking
check 'Public API DNS' getent ahostsv4 "api.$domain"
check 'Internal API DNS' getent ahostsv4 "api-int.$domain"
check 'Wildcard ingress DNS' getent ahostsv4 "probe.apps.$domain"

if (( failures > 0 )); then
  printf '\n%d command(s) failed. Review the first failed stage.\n' "$failures" >&2
  exit 1
fi
printf '\nProbes completed. Compare bridge, IPs, DNS, and clock output with the approved inventory.\n'
