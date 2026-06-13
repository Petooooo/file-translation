#!/usr/bin/env bash
set -Eeuo pipefail

PATH="$HOME/.local/bin:$PATH"

CLUSTER_NAME="${CLUSTER_NAME:-file-translation-manual-airgap}"
KUBE_CONTEXT="${KUBE_CONTEXT:-k3d-${CLUSTER_NAME}}"
DEPS_NAMESPACE="${DEPS_NAMESPACE:-file-translation-deps}"
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
PID_DIR="${PID_DIR:-/tmp/file-translation-manual-airgap-portforwards}"

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

warn() {
  printf '[WARN] %s\n' "$1" >&2
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

die() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

require_cmd() {
  has_cmd "$1" || die "$1 is required"
}

stop_existing() {
  if [ ! -d "$PID_DIR" ]; then
    return
  fi
  for pid_file in "$PID_DIR"/*.pid; do
    [ -e "$pid_file" ] || continue
    pid="$(cat "$pid_file")"
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
    fi
  done
  rm -rf "$PID_DIR"
}

start_forward() {
  name="$1"
  namespace="$2"
  service="$3"
  local_port="$4"
  remote_port="$5"

  if ! kubectl --context "$KUBE_CONTEXT" -n "$namespace" get "svc/${service}" >/dev/null 2>&1; then
    warn "Skipping ${name}; service ${namespace}/${service} does not exist"
    return
  fi

  log_file="${PID_DIR}/${name}.log"
  pid_file="${PID_DIR}/${name}.pid"
  note "Forwarding ${name}: localhost:${local_port} -> ${namespace}/svc/${service}:${remote_port}"
  if has_cmd setsid; then
    setsid kubectl --context "$KUBE_CONTEXT" -n "$namespace" port-forward "svc/${service}" "${local_port}:${remote_port}" >"$log_file" 2>&1 </dev/null &
  else
    nohup kubectl --context "$KUBE_CONTEXT" -n "$namespace" port-forward "svc/${service}" "${local_port}:${remote_port}" >"$log_file" 2>&1 </dev/null &
  fi
  pid="$!"
  printf '%s\n' "$pid" >"$pid_file"
  sleep 0.5
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    warn "Port-forward ${name} exited early; see ${log_file}"
  fi
}

require_cmd kubectl

stop_existing
mkdir -p "$PID_DIR"

start_forward minio-api "$DEPS_NAMESPACE" manual-minio 19000 9000
start_forward minio-console "$DEPS_NAMESPACE" manual-minio 19001 9001
start_forward rabbitmq-amqp "$DEPS_NAMESPACE" manual-rabbitmq 25672 5672
start_forward rabbitmq-web "$DEPS_NAMESPACE" manual-rabbitmq 15672 15672
start_forward postgresql "$DEPS_NAMESPACE" manual-postgresql 15432 5432
start_forward pgadmin-web "$DEPS_NAMESPACE" manual-pgadmin 15050 80
start_forward argocd-web "$ARGOCD_NAMESPACE" argocd-server 18080 443

pass "Manual airgap port-forwards started; PID files are in ${PID_DIR}"
cat <<EOF

Endpoints:
  MinIO API:      http://localhost:19000
  MinIO Console:  http://localhost:19001
  RabbitMQ AMQP:  localhost:25672
  RabbitMQ Web:   http://localhost:15672
  PostgreSQL:     localhost:15432
  pgAdmin Web:    http://localhost:15050
  ArgoCD Web:     https://localhost:18080

Stop:
  scripts/dev/manual-airgap-stop-port-forward.sh
EOF
