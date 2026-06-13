#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PATH="$HOME/.local/bin:$PATH"

RELEASE="${RELEASE:-file-translation}"
NAMESPACE="${NAMESPACE:-file-translation}"
JOB_SERVICE_NAME="${JOB_SERVICE_NAME:-${RELEASE}-job-service}"
MINIO_NAME="${MINIO_NAME:-${RELEASE}-minio}"
SECRET_NAME="${SECRET_NAME:-${RELEASE}-secrets}"
CONFIG_NAME="${CONFIG_NAME:-${RELEASE}-config}"
JOB_SERVICE_PORT="${JOB_SERVICE_PORT:-18080}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"
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

kubectl -n "$NAMESPACE" get deploy "${JOB_SERVICE_NAME}" >/dev/null
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-queue-init" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-minio-init" --timeout="${TIMEOUT_SECONDS}s"
kubectl -n "$NAMESPACE" rollout status deployment \
  -l "app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/part-of=file-translation" \
  --timeout="${TIMEOUT_SECONDS}s"

note "Port-forwarding job-service to 127.0.0.1:${JOB_SERVICE_PORT}"
kubectl -n "$NAMESPACE" port-forward "svc/${JOB_SERVICE_NAME}" "${JOB_SERVICE_PORT}:8080" >/tmp/file-translation-helm-job-service-port-forward.log 2>&1 &
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
if ready.get("overall_status") not in {"healthy", "degraded"}:
    raise SystemExit(f"unexpected /readyz payload: {ready}")
if admin.get("overall_status") not in {"healthy", "degraded"}:
    raise SystemExit(f"unexpected /admin/health payload: {admin}")
if "dependencies" not in admin or "queue_summary" not in admin:
    raise SystemExit(f"/admin/health is missing dependency or queue summary: {admin}")
PY

case "$admin_page" in
  *"File Translation Admin"*|*"admin"*) pass "Admin UI page loaded" ;;
  *) die "Admin UI page did not contain expected text" ;;
esac

pass "job-service health/readiness/admin checks passed"

if [ "$RUN_ROUTE_E2E" != "1" ]; then
  pass "Helm local smoke completed without route E2E"
  exit 0
fi

MINIO_ACCESS_KEY="$(kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.MINIO_ACCESS_KEY}' | base64 -d)"
MINIO_SECRET_KEY="$(kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.MINIO_SECRET_KEY}' | base64 -d)"
MINIO_BUCKET="$(kubectl -n "$NAMESPACE" get configmap "$CONFIG_NAME" -o jsonpath='{.data.MINIO_BUCKET}')"
MINIO_ENDPOINT="http://${MINIO_NAME}:9000"
JOB_SERVICE_URL="http://${JOB_SERVICE_NAME}:8080"
USER_ID="${USER_ID:-12345678}"
FILE_ID="${FILE_ID:-helmhwpxroute}"
INPUT_KEY="${INPUT_KEY:-$(date +%F)/${USER_ID}/${FILE_ID}/input/original.hwpx}"

note "Running in-cluster HWPX route E2E driver pod"
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
create_sample_hwpx(path, ["Translate me from the Helm local stack"])
client = minio_client()
if not client.bucket_exists(bucket):
    client.make_bucket(bucket)
client.fput_object(bucket, input_key, str(path), content_type="application/octet-stream")

payload = {
    "user_id": os.environ["USER_ID"],
    "file_id": os.environ["FILE_ID"],
    "input_type": "hwpx",
    "source_lang": "en",
    "target_lang": "ko",
    "original_filename": "helm-smoke.hwpx",
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
for queue in queues.get("queues", []):
    if queue.get("kind") == "command" and queue.get("message_count") not in {0, None}:
        raise SystemExit(f"stale command queue detected: {queue}")

print(json.dumps({"job_id": job_id, "status": "completed", "final_hwpx_key": job["final_hwpx_key"]}, sort_keys=True))
PY

pass "Helm local HWPX route E2E smoke passed"
