#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PATH="$HOME/.local/bin:$PATH"

RELEASE="${RELEASE:-file-translation-closed}"
NAMESPACE="${NAMESPACE:-file-translation-closed-rehearsal}"
DEPS_NAMESPACE="${DEPS_NAMESPACE:-file-translation-closed-rehearsal-deps}"
JOB_SERVICE_NAME="${JOB_SERVICE_NAME:-${RELEASE}-job-service}"
SECRET_NAME="${SECRET_NAME:-file-translation-closed-rehearsal-secrets}"
CONFIG_NAME="${CONFIG_NAME:-${RELEASE}-config}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-ft-closed-postgresql}"
RABBITMQ_SERVICE="${RABBITMQ_SERVICE:-ft-closed-rabbitmq}"
MINIO_SERVICE="${MINIO_SERVICE:-ft-closed-minio}"
JOB_SERVICE_PORT="${JOB_SERVICE_PORT:-18090}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"
HWPX_DRIVER_IMAGE="${HWPX_DRIVER_IMAGE:-petoo/file-translation-hwpx-worker:0.1.0}"
RUN_ROUTE_E2E="${RUN_ROUTE_E2E:-1}"

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
  kubectl -n "$NAMESPACE" delete pod "${RELEASE}-hwpx-route-driver" --ignore-not-found >/dev/null 2>&1 || true
  return "$status"
}
trap cleanup EXIT

has_cmd kubectl || die "kubectl is required"
has_cmd curl || die "curl is required"
has_cmd python3 || die "python3 is required"

note "Checking external dependency Deployments"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${POSTGRES_SERVICE}" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${RABBITMQ_SERVICE}" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${MINIO_SERVICE}" --timeout="${TIMEOUT_SECONDS}s"

kubectl -n "$NAMESPACE" get deploy "$JOB_SERVICE_NAME" >/dev/null
kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" >/dev/null
if [ "$SECRET_NAME" != "${RELEASE}-secrets" ] && kubectl -n "$NAMESPACE" get secret "${RELEASE}-secrets" >/dev/null 2>&1; then
  die "Chart-created Secret should not exist when secrets.existingSecret is used: ${RELEASE}-secrets"
fi

for bundled in "${RELEASE}-postgresql" "${RELEASE}-rabbitmq" "${RELEASE}-minio"; do
  if kubectl -n "$NAMESPACE" get deployment "$bundled" >/dev/null 2>&1; then
    die "Bundled dependency Deployment should be disabled but exists: ${bundled}"
  fi
done

kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-queue-init" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-minio-init" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$NAMESPACE" rollout status deployment \
  -l "app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/part-of=file-translation" \
  --timeout="${TIMEOUT_SECONDS}s"

note "Validating rendered runtime ConfigMap and image overrides"
config_json="$(kubectl -n "$NAMESPACE" get configmap "$CONFIG_NAME" -o json)"
python3 - "$config_json" "$DEPS_NAMESPACE" <<'PY'
import json
import sys

config = json.loads(sys.argv[1])["data"]
deps_namespace = sys.argv[2]

expected = {
    "APP_ENV": "closed-network-local-rehearsal",
    "RABBITMQ_HOST": f"ft-closed-rabbitmq.{deps_namespace}.svc.cluster.local",
    "POSTGRES_HOST": f"ft-closed-postgresql.{deps_namespace}.svc.cluster.local",
    "POSTGRES_DB": "file_translation",
    "MINIO_ENDPOINT": f"http://ft-closed-minio.{deps_namespace}.svc.cluster.local:9000",
    "MINIO_BUCKET": "file-translation-closed-rehearsal",
    "EMAIL_PROVIDER": "mock",
    "EMAIL_API_BASE_URL": "http://mail-api.rehearsal.invalid",
    "PDF2DOCX_IMAGE": "petoo/pdf2docx:0.5.13-py311-static",
    "PDF2HWPX_PROVIDER": "placeholder",
    "PDF2HWPX_CUSTOM_LIBRARY_ENABLED": "false",
}
for key, value in expected.items():
    actual = config.get(key)
    if actual != value:
        raise SystemExit(f"{key} expected {value!r}, got {actual!r}")
PY

for pair in \
  "${RELEASE}-email-worker=petoo/file-translation-email-worker:0.1.0" \
  "${RELEASE}-pdf2hwpx-worker=petoo/file-translation-pdf2hwpx-worker:0.1.0" \
  "${RELEASE}-pdf2docx-worker=petoo/file-translation-pdf2docx-worker:0.1.0"; do
  deployment="${pair%%=*}"
  expected="${pair#*=}"
  actual="$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath='{.spec.template.spec.containers[0].image}')"
  if [ "$actual" != "$expected" ]; then
    die "Unexpected image for ${deployment}: expected ${expected}, got ${actual}"
  fi
done

note "Port-forwarding job-service to 127.0.0.1:${JOB_SERVICE_PORT}"
kubectl -n "$NAMESPACE" port-forward "svc/${JOB_SERVICE_NAME}" "${JOB_SERVICE_PORT}:8080" >/tmp/file-translation-closed-job-service-port-forward.log 2>&1 &
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
admin_page="$(curl -fsS "http://127.0.0.1:${JOB_SERVICE_PORT}/admin")"

python3 - "$health_json" "$ready_json" "$admin_health_json" <<'PY'
import json
import sys

health = json.loads(sys.argv[1])
ready = json.loads(sys.argv[2])
admin = json.loads(sys.argv[3])

if health.get("status") != "ok":
    raise SystemExit(f"unexpected /healthz payload: {health}")
for payload_name, payload in {"readyz": ready, "admin_health": admin}.items():
    if payload.get("overall_status") != "healthy":
        raise SystemExit(f"{payload_name} is not healthy: {payload}")
    dependencies = payload.get("dependencies", {})
    for name in ("postgresql", "rabbitmq", "minio"):
        if dependencies.get(name, {}).get("status") != "healthy":
            raise SystemExit(f"{payload_name} dependency {name} is not healthy: {dependencies.get(name)}")

queue_summary = admin.get("queue_summary", {})
if queue_summary.get("status") != "healthy" or queue_summary.get("missing_count") != 0:
    raise SystemExit(f"queue summary is not healthy: {queue_summary}")
if admin.get("environment") != "closed-network-local-rehearsal":
    raise SystemExit(f"unexpected environment: {admin.get('environment')}")
PY

case "$admin_page" in
  *"File Translation Admin"*|*"admin"*) pass "Admin UI page loaded" ;;
  *) die "Admin UI page did not contain expected text" ;;
esac

pass "closed rehearsal health/readiness/admin checks passed"

if [ "$RUN_ROUTE_E2E" != "1" ]; then
  pass "Closed rehearsal smoke completed without route E2E"
  exit 0
fi

MINIO_ACCESS_KEY="$(kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.MINIO_ACCESS_KEY}' | base64 -d)"
MINIO_SECRET_KEY="$(kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.MINIO_SECRET_KEY}' | base64 -d)"
MINIO_BUCKET="$(kubectl -n "$NAMESPACE" get configmap "$CONFIG_NAME" -o jsonpath='{.data.MINIO_BUCKET}')"
MINIO_ENDPOINT="$(kubectl -n "$NAMESPACE" get configmap "$CONFIG_NAME" -o jsonpath='{.data.MINIO_ENDPOINT}')"
JOB_SERVICE_URL="http://${JOB_SERVICE_NAME}:8080"
USER_ID="${USER_ID:-12345678}"
FILE_ID="${FILE_ID:-closedhwpxroute}"
INPUT_KEY="${INPUT_KEY:-$(date +%F)/${USER_ID}/${FILE_ID}/input/original.hwpx}"

note "Running in-cluster HWPX route E2E driver pod against external MinIO"
kubectl -n "$NAMESPACE" delete pod "${RELEASE}-hwpx-route-driver" --ignore-not-found >/dev/null 2>&1 || true
kubectl -n "$NAMESPACE" run "${RELEASE}-hwpx-route-driver" \
  --rm \
  -i \
  --restart=Never \
  --image="$HWPX_DRIVER_IMAGE" \
  --image-pull-policy=IfNotPresent \
  --env="JOB_SERVICE_URL=${JOB_SERVICE_URL}" \
  --env="MINIO_ENDPOINT=${MINIO_ENDPOINT}" \
  --env="MINIO_BUCKET=${MINIO_BUCKET}" \
  --env="MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  --env="MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  --env="USER_ID=${USER_ID}" \
  --env="FILE_ID=${FILE_ID}" \
  --env="INPUT_KEY=${INPUT_KEY}" \
  --command -- python - <<'PY'
import json
import os
import sys
import time
from pathlib import Path
from urllib import request
from urllib.parse import urlparse

sys.path.insert(0, "/app/service")

from hwpx_worker.hwpx_xml import create_sample_hwpx
from minio import Minio


def http_json(method, path, payload=None):
    base = os.environ["JOB_SERVICE_URL"].rstrip("/")
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    req = request.Request(f"{base}{path}", data=body, method=method, headers=headers)
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def minio_client():
    endpoint = os.environ["MINIO_ENDPOINT"]
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    host = parsed.netloc or parsed.path
    secure = parsed.scheme == "https"
    return Minio(
        host,
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=secure,
    )


bucket = os.environ["MINIO_BUCKET"]
input_key = os.environ["INPUT_KEY"]
path = Path("/tmp/original.hwpx")
create_sample_hwpx(path, ["Translate me from the closed-network rehearsal stack"])
client = minio_client()
if not client.bucket_exists(bucket):
    raise SystemExit(f"expected bucket to exist after Helm minio-init job: {bucket}")
client.fput_object(bucket, input_key, str(path), content_type="application/octet-stream")

payload = {
    "user_id": os.environ["USER_ID"],
    "file_id": os.environ["FILE_ID"],
    "input_type": "hwpx",
    "source_lang": "en",
    "target_lang": "ko",
    "original_filename": "closed-rehearsal-smoke.hwpx",
    "input_object_key": input_key,
}
created = http_json("POST", "/jobs", payload)
job = created["job"]
job_id = job["job_id"]
deadline = time.time() + 180
while time.time() < deadline:
    job = http_json("GET", f"/jobs/{job_id}")
    if job.get("status") in {"completed", "failed", "cancelled", "expired"}:
        break
    time.sleep(2)
else:
    raise SystemExit(f"job did not reach terminal state: {job_id}")

if job.get("status") != "completed":
    raise SystemExit(f"job did not complete: {json.dumps(job, sort_keys=True)}")
if job.get("current_stage") != "completed":
    raise SystemExit(f"unexpected current_stage: {job.get('current_stage')}")

expected_keys = [
    job.get("final_docx_key"),
    job.get("final_pdf_key"),
    job.get("final_hwpx_key"),
    job.get("artifacts", {}).get("email_report"),
]
missing = [key for key in expected_keys if not key]
if missing:
    raise SystemExit(f"missing final artifact keys in job payload: {job}")

for key in expected_keys:
    client.stat_object(bucket, key)

queues = http_json("GET", "/admin/queues")
if queues.get("status") != "healthy":
    raise SystemExit(f"unexpected queue status: {queues}")
for queue in queues.get("queues", []):
    if queue.get("kind") == "command" and queue.get("message_count") not in {0, None}:
        raise SystemExit(f"stale command queue detected: {queue}")

print(json.dumps({"job_id": job_id, "status": "completed", "final_hwpx_key": job["final_hwpx_key"]}, sort_keys=True))
PY

pass "Closed rehearsal HWPX route E2E smoke passed"
