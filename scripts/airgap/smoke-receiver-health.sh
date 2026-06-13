#!/usr/bin/env bash
set -Eeuo pipefail

RELEASE="${RELEASE:-file-translation-airgap}"
NAMESPACE="${NAMESPACE:-file-translation-airgap}"
JOB_SERVICE_NAME="${JOB_SERVICE_NAME:-${RELEASE}-job-service}"
JOB_SERVICE_PORT="${JOB_SERVICE_PORT:-18091}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

die() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

PF_PID=""
cleanup() {
  status=$?
  if [ -n "$PF_PID" ]; then
    kill "$PF_PID" >/dev/null 2>&1 || true
    wait "$PF_PID" >/dev/null 2>&1 || true
  fi
  return "$status"
}
trap cleanup EXIT

has_cmd kubectl || die "kubectl is required"
has_cmd curl || die "curl is required"
has_cmd python3 || die "python3 is required"

kubectl -n "$NAMESPACE" get deploy "$JOB_SERVICE_NAME" >/dev/null
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-queue-init" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-minio-init" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$NAMESPACE" rollout status deployment \
  -l "app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/part-of=file-translation" \
  --timeout="${TIMEOUT_SECONDS}s"

note "Port-forwarding job-service to 127.0.0.1:${JOB_SERVICE_PORT}"
kubectl -n "$NAMESPACE" port-forward "svc/${JOB_SERVICE_NAME}" "${JOB_SERVICE_PORT}:8080" >/tmp/file-translation-airgap-receiver-port-forward.log 2>&1 &
PF_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${JOB_SERVICE_PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

health_json="$(curl -fsS "http://127.0.0.1:${JOB_SERVICE_PORT}/healthz")"
ready_json="$(curl -fsS "http://127.0.0.1:${JOB_SERVICE_PORT}/readyz")"
admin_health_json="$(curl -fsS "http://127.0.0.1:${JOB_SERVICE_PORT}/admin/health")"

python3 - "$health_json" "$ready_json" "$admin_health_json" <<'PY'
import json
import sys

health = json.loads(sys.argv[1])
ready = json.loads(sys.argv[2])
admin = json.loads(sys.argv[3])

if health.get("status") != "ok":
    raise SystemExit(f"unexpected /healthz payload: {health}")

for name, payload in {"readyz": ready, "admin_health": admin}.items():
    if payload.get("overall_status") != "healthy":
        raise SystemExit(f"{name} is not healthy: {payload}")
    dependencies = payload.get("dependencies", {})
    for dependency in ("postgresql", "rabbitmq", "minio"):
        if dependencies.get(dependency, {}).get("status") != "healthy":
            raise SystemExit(f"{name} dependency {dependency} is not healthy: {dependencies.get(dependency)}")

queue_summary = admin.get("queue_summary", {})
if queue_summary.get("status") != "healthy" or queue_summary.get("missing_count") != 0:
    raise SystemExit(f"queue summary is not healthy: {queue_summary}")
PY

pass "Receiver rehearsal health/readiness/admin checks passed"
