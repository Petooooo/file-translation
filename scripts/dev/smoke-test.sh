#!/usr/bin/env bash
set -Eeuo pipefail

NAMESPACE="${NAMESPACE:-file-translation}"
DNS_IMAGE="${DNS_IMAGE:-busybox:1.36}"
DNS_POD="${DNS_POD:-ft-dns-smoke}"
DNS_NAME="${DNS_NAME:-kubernetes.default.svc.cluster.local}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-test.sh

Runs a local Kubernetes smoke test for the project namespace and cluster DNS.

Environment variables:
  NAMESPACE   Project namespace. Default: file-translation
  DNS_IMAGE   Image used for DNS lookup. Default: busybox:1.36
  DNS_POD     Temporary pod name. Default: ft-dns-smoke
  DNS_NAME    DNS name to resolve. Default: kubernetes.default.svc.cluster.local
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

die() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

cleanup() {
  if has_cmd kubectl; then
    kubectl -n "$NAMESPACE" delete pod "$DNS_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

has_cmd kubectl || die "kubectl is required. Run scripts/dev/check-env.sh first."

note "Checking Kubernetes API"
kubectl cluster-info >/dev/null
pass "Kubernetes API is reachable"

note "Checking node readiness"
kubectl get nodes -o wide

note "Checking namespace: ${NAMESPACE}"
kubectl get namespace "$NAMESPACE" >/dev/null
pass "Namespace exists: ${NAMESPACE}"

note "Checking CoreDNS deployment"
kubectl -n kube-system get deployment coredns >/dev/null
pass "CoreDNS deployment exists"

note "Running DNS lookup pod with image ${DNS_IMAGE}"
kubectl -n "$NAMESPACE" delete pod "$DNS_POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
kubectl -n "$NAMESPACE" run "$DNS_POD" \
  --image="$DNS_IMAGE" \
  --restart=Never \
  --rm \
  -i \
  --quiet \
  --command -- nslookup "$DNS_NAME"

pass "Cluster DNS resolved ${DNS_NAME}"
pass "Local Kubernetes smoke test complete"
