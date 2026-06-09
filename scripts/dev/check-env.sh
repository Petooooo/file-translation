#!/usr/bin/env bash
set -u

CLUSTER_PROVIDER="${CLUSTER_PROVIDER:-k3d}"
CLUSTER_NAME="${CLUSTER_NAME:-file-translation-dev}"
NAMESPACE="${NAMESPACE:-file-translation}"

failures=0
warnings=0

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

warn() {
  warnings=$((warnings + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  failures=$((failures + 1))
  printf '[FAIL] %s\n' "$1"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

first_line() {
  printf '%s\n' "$1" | sed -n '1p'
}

cmd_version() {
  case "$1" in
    docker)
      docker --version 2>/dev/null
      ;;
    docker-compose)
      docker compose version 2>/dev/null
      ;;
    kubectl)
      kubectl version --client 2>/dev/null
      ;;
    helm)
      helm version --short 2>/dev/null
      ;;
    k3d)
      k3d version 2>/dev/null
      ;;
    kind)
      kind version 2>/dev/null
      ;;
    k3s)
      k3s --version 2>/dev/null
      ;;
    *)
      "$1" --version 2>/dev/null
      ;;
  esac
}

require_cmd() {
  cmd="$1"
  description="$2"

  if has_cmd "$cmd"; then
    version="$(cmd_version "$cmd" || true)"
    if [ -n "$version" ]; then
      pass "$description: $(first_line "$version")"
    else
      pass "$description: installed"
    fi
  else
    fail "$description: command not found ($cmd)"
  fi
}

print_install_hints() {
  cat <<'EOF'

Install hints:

Helm:
  curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
  chmod 700 get_helm.sh
  ./get_helm.sh

k3d:
  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

kind fallback:
  curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.32.0/kind-linux-amd64
  chmod +x ./kind
  sudo mv ./kind /usr/local/bin/kind
EOF
}

note "Checking local development prerequisites"
note "CLUSTER_PROVIDER=${CLUSTER_PROVIDER}"
note "CLUSTER_NAME=${CLUSTER_NAME}"
note "NAMESPACE=${NAMESPACE}"

require_cmd docker "Docker client"

if has_cmd docker; then
  if docker info >/dev/null 2>&1; then
    pass "Docker server: reachable"
  else
    fail "Docker server: not reachable. Start Docker Desktop or the Docker daemon."
  fi

  if docker compose version >/dev/null 2>&1; then
    version="$(docker compose version 2>/dev/null || true)"
    pass "Docker Compose: $(first_line "$version")"
  else
    warn "Docker Compose: unavailable. It is not required for k3d, but useful for local diagnostics."
  fi
fi

require_cmd kubectl "kubectl client"
require_cmd helm "Helm client"

case "$CLUSTER_PROVIDER" in
  k3d)
    require_cmd k3d "k3d local cluster tool"
    if has_cmd kind; then
      version="$(cmd_version kind || true)"
      pass "kind fallback: $(first_line "$version")"
    else
      warn "kind fallback: command not found. This is optional while k3d is the selected provider."
    fi
    ;;
  kind)
    require_cmd kind "kind local cluster tool"
    if has_cmd k3d; then
      version="$(cmd_version k3d || true)"
      pass "k3d primary option: $(first_line "$version")"
    else
      warn "k3d primary option: command not found. This is acceptable only if kind is intentionally selected."
    fi
    ;;
  *)
    fail "Unsupported CLUSTER_PROVIDER=${CLUSTER_PROVIDER}. Use k3d or kind."
    ;;
esac

if has_cmd k3s; then
  version="$(cmd_version k3s || true)"
  pass "Native k3s: $(first_line "$version")"
else
  warn "Native k3s: command not found. This is expected for the default Docker-based local setup."
fi

if has_cmd kubectl; then
  context="$(kubectl config current-context 2>/dev/null || true)"
  if [ -n "$context" ]; then
    pass "kubectl current context: ${context}"
  else
    warn "kubectl current context: not set"
  fi

  cluster_info="$(kubectl cluster-info 2>&1)"
  cluster_rc=$?
  if [ "$cluster_rc" -eq 0 ]; then
    pass "Kubernetes API: reachable"
  else
    warn "Kubernetes API: not reachable yet. Run scripts/dev/bootstrap-cluster.sh after installing missing tools."
    printf '%s\n' "$cluster_info" | sed 's/^/[KUBECTL] /'
  fi
fi

if [ "$failures" -gt 0 ]; then
  print_install_hints
  printf '\nEnvironment check failed: %s failure(s), %s warning(s).\n' "$failures" "$warnings"
  exit 1
fi

printf '\nEnvironment check passed with %s warning(s).\n' "$warnings"
printf 'Next: scripts/dev/bootstrap-cluster.sh\n'
