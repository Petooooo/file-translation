#!/usr/bin/env bash
set -Eeuo pipefail

CLUSTER_PROVIDER="${CLUSTER_PROVIDER:-k3d}"
CLUSTER_NAME="${CLUSTER_NAME:-file-translation-dev}"
NAMESPACE="${NAMESPACE:-file-translation}"
K3D_AGENTS="${K3D_AGENTS:-1}"
K3D_API_PORT="${K3D_API_PORT:-127.0.0.1:6550}"
K3D_HTTP_PORT="${K3D_HTTP_PORT:-8080}"
KIND_HTTP_PORT="${KIND_HTTP_PORT:-8080}"
NODE_READY_TIMEOUT="${NODE_READY_TIMEOUT:-180s}"
COREDNS_TIMEOUT="${COREDNS_TIMEOUT:-180s}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/bootstrap-cluster.sh

Creates or reuses a local Kubernetes cluster and ensures the project namespace exists.

Environment variables:
  CLUSTER_PROVIDER     k3d or kind. Default: k3d
  CLUSTER_NAME         Local cluster name. Default: file-translation-dev
  NAMESPACE            Project namespace. Default: file-translation
  K3D_AGENTS           Number of k3d agent nodes. Default: 1
  K3D_API_PORT         k3d API listen address. Default: 127.0.0.1:6550
  K3D_HTTP_PORT        Host port mapped to k3d load balancer port 80. Default: 8080
  KIND_HTTP_PORT       Host port mapped to kind control-plane port 80. Default: 8080
  NODE_READY_TIMEOUT   Node readiness wait timeout. Default: 180s
  COREDNS_TIMEOUT      CoreDNS rollout wait timeout. Default: 180s
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

require_cmd() {
  if ! has_cmd "$1"; then
    die "$1 is required. Run scripts/dev/check-env.sh for install commands."
  fi
}

ensure_docker() {
  require_cmd docker
  docker info >/dev/null 2>&1 || die "Docker server is not reachable. Start Docker Desktop or the Docker daemon."
}

ensure_kubectl() {
  require_cmd kubectl
}

k3d_cluster_exists() {
  k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1
}

create_or_reuse_k3d() {
  require_cmd k3d

  if k3d_cluster_exists; then
    pass "k3d cluster already exists: ${CLUSTER_NAME}"
  else
    note "Creating k3d cluster: ${CLUSTER_NAME}"
    k3d cluster create "$CLUSTER_NAME" \
      --agents "$K3D_AGENTS" \
      --api-port "$K3D_API_PORT" \
      --port "${K3D_HTTP_PORT}:80@loadbalancer"
  fi

  kubectl config use-context "k3d-${CLUSTER_NAME}" >/dev/null
}

kind_cluster_exists() {
  kind get clusters 2>/dev/null | grep -Fx "$CLUSTER_NAME" >/dev/null 2>&1
}

create_or_reuse_kind() {
  require_cmd kind

  if kind_cluster_exists; then
    pass "kind cluster already exists: ${CLUSTER_NAME}"
  else
    note "Creating kind cluster: ${CLUSTER_NAME}"
    tmp_config="$(mktemp)"
    cleanup_kind_config() {
      rm -f "$tmp_config"
    }
    trap cleanup_kind_config RETURN

    cat >"$tmp_config" <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 80
        hostPort: ${KIND_HTTP_PORT}
        protocol: TCP
EOF

    kind create cluster --name "$CLUSTER_NAME" --config "$tmp_config"
  fi

  kubectl config use-context "kind-${CLUSTER_NAME}" >/dev/null
}

ensure_namespace() {
  note "Ensuring namespace exists: ${NAMESPACE}"
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
}

wait_for_cluster() {
  note "Waiting for Kubernetes nodes to become Ready"
  kubectl wait --for=condition=Ready nodes --all --timeout="$NODE_READY_TIMEOUT"

  note "Waiting for CoreDNS rollout"
  kubectl -n kube-system rollout status deployment/coredns --timeout="$COREDNS_TIMEOUT"
}

note "Bootstrapping local Kubernetes"
note "CLUSTER_PROVIDER=${CLUSTER_PROVIDER}"
note "CLUSTER_NAME=${CLUSTER_NAME}"
note "NAMESPACE=${NAMESPACE}"

ensure_docker
ensure_kubectl

case "$CLUSTER_PROVIDER" in
  k3d)
    create_or_reuse_k3d
    ;;
  kind)
    create_or_reuse_kind
    ;;
  *)
    die "Unsupported CLUSTER_PROVIDER=${CLUSTER_PROVIDER}. Use k3d or kind."
    ;;
esac

wait_for_cluster
ensure_namespace

pass "Local cluster bootstrap complete"
printf 'Next: scripts/dev/smoke-test.sh\n'
