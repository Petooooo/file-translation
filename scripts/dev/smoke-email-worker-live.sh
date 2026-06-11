#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-email-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-email-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-email-rabbitmq-live}"
JOB_SERVICE_CONTAINER="${JOB_SERVICE_CONTAINER:-ft-email-job-service-live}"
WORKER_CONTAINER="${WORKER_CONTAINER:-ft-email-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-email-seed-live}"
PUBLISH_CONTAINER="${PUBLISH_CONTAINER:-ft-email-publish-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
WORKER_IMAGE="${WORKER_IMAGE:-petoo/file-translation-email-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"

OBJECT_PREFIX="${OBJECT_PREFIX:-2026-01-21/12345678/emailsmoke1}"
JOB_ID="${JOB_ID:-live-email-smoke}"
USER_ID="${USER_ID:-12345678}"
OUT_DIR="${OUT_DIR:-out/email-worker-live}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUE="${COMMAND_QUEUE:-q.commands.email_send}"
EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-email-worker-live.sh

Runs a Docker-based live smoke for:
  RabbitMQ command -> email-worker mock provider -> MinIO email_report.json -> RabbitMQ event

Environment variables:
  NETWORK                 Docker network. Default: ft-email-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  WORKER_IMAGE            Default: petoo/file-translation-email-worker:0.1.0
  MINIO_ACCESS_KEY        Default: minioadmin
  MINIO_SECRET_KEY        Default: minioadmin
  RABBITMQ_USERNAME       Default: guest
  RABBITMQ_PASSWORD       Default: guest
  MINIO_BUCKET            Default: file-translation
  OBJECT_PREFIX           Default: 2026-01-21/12345678/emailsmoke1
  JOB_ID                  Default: live-email-smoke
  OUT_DIR                 Default: out/email-worker-live
  KEEP_LIVE_SMOKE=1       Keep containers/network after the smoke.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

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

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    docker logs "$WORKER_CONTAINER" >/tmp/email-worker-live.log 2>&1 || true
    if [ -s /tmp/email-worker-live.log ]; then
      printf '[INFO] worker logs:\n' >&2
      cat /tmp/email-worker-live.log >&2
    fi
    docker logs "$JOB_SERVICE_CONTAINER" >/tmp/email-job-service-live.log 2>&1 || true
    if [ -s /tmp/email-job-service-live.log ]; then
      printf '[INFO] fake job-service logs:\n' >&2
      cat /tmp/email-job-service-live.log >&2
    fi
  fi
  if [ "$KEEP_LIVE_SMOKE" != "1" ]; then
    docker rm -f \
      "$PUBLISH_CONTAINER" \
      "$SEED_CONTAINER" \
      "$WORKER_CONTAINER" \
      "$JOB_SERVICE_CONTAINER" \
      "$RABBITMQ_CONTAINER" \
      "$MINIO_CONTAINER" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
  else
    note "KEEP_LIVE_SMOKE=1; keeping containers and network"
  fi
  return "$status"
}

trap cleanup EXIT

has_cmd docker || die "docker is required"
docker info >/dev/null || die "Docker server is not reachable"

note "Preparing Docker network ${NETWORK}"
docker rm -f \
  "$PUBLISH_CONTAINER" \
  "$SEED_CONTAINER" \
  "$WORKER_CONTAINER" \
  "$JOB_SERVICE_CONTAINER" \
  "$RABBITMQ_CONTAINER" \
  "$MINIO_CONTAINER" >/dev/null 2>&1 || true
docker network rm "$NETWORK" >/dev/null 2>&1 || true
docker network create "$NETWORK" >/dev/null

note "Starting MinIO ${MINIO_IMAGE}"
docker run -d \
  --name "$MINIO_CONTAINER" \
  --network "$NETWORK" \
  --network-alias minio \
  -e "MINIO_ROOT_USER=${MINIO_ACCESS_KEY}" \
  -e "MINIO_ROOT_PASSWORD=${MINIO_SECRET_KEY}" \
  "$MINIO_IMAGE" server /data >/dev/null

note "Starting RabbitMQ ${RABBITMQ_IMAGE}"
docker run -d \
  --name "$RABBITMQ_CONTAINER" \
  --hostname rabbitmq \
  --network "$NETWORK" \
  --network-alias rabbitmq \
  -e "RABBITMQ_DEFAULT_USER=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}" \
  "$RABBITMQ_IMAGE" >/dev/null

note "Starting fake job-service sendability endpoint"
docker run -d \
  --name "$JOB_SERVICE_CONTAINER" \
  --network "$NETWORK" \
  --network-alias job-service \
  -e "JOB_ID=${JOB_ID}" \
  -e "USER_ID=${USER_ID}" \
  -e "OBJECT_PREFIX=${OBJECT_PREFIX}" \
  "$WORKER_IMAGE" \
  python -c '
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

job_id = os.environ["JOB_ID"]
user_id = os.environ["USER_ID"]
object_prefix = os.environ["OBJECT_PREFIX"].strip("/")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        expected_path = f"/jobs/{job_id}/sendability"
        if self.path != expected_path:
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "job_id": job_id,
            "sendable": True,
            "status": "running",
            "current_stage": "email_send",
            "reason": None,
            "input_type": "docx",
            "user_id": user_id,
            "file_id": "emailsmoke1",
            "object_prefix": object_prefix,
            "artifacts": {
                "final_docx": f"{object_prefix}/05_export/final.docx",
                "final_pdf": f"{object_prefix}/05_export/final.pdf",
                "final_hwpx": f"{object_prefix}/06_hwpx/final.hwpx",
            },
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return

ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
' >/dev/null

note "Waiting for MinIO/RabbitMQ and declaring queues"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
docker run --rm -i \
  --name "$SEED_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "COMMAND_QUEUE=${COMMAND_QUEUE}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  "$WORKER_IMAGE" \
  python - <<'PY'
import os
import time

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]

for attempt in range(60):
    try:
        client = Minio(
            os.environ["MINIO_ENDPOINT"],
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            secure=False,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
for attempt in range(60):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
        )
        channel = connection.channel()
        for queue in [
            os.environ["COMMAND_QUEUE"],
            os.environ["EVENT_COMPLETED_QUEUE"],
            os.environ["EVENT_FAILED_QUEUE"],
        ]:
            channel.queue_declare(queue=queue, durable=True)
            channel.queue_purge(queue=queue)
        connection.close()
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
PY

note "Starting email-worker consumer"
docker run -d \
  --name "$WORKER_CONTAINER" \
  --network "$NETWORK" \
  -e "EMAIL_PROVIDER=mock" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$WORKER_IMAGE" \
  python /app/service/worker.py --consume >/dev/null

note "Publishing email_send command and waiting for completed event"
docker run --rm -i \
  --name "$PUBLISH_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "OBJECT_PREFIX=${OBJECT_PREFIX}" \
  -e "JOB_ID=${JOB_ID}" \
  -e "COMMAND_QUEUE=${COMMAND_QUEUE}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$WORKER_IMAGE" \
  python - <<'PY'
import json
import os
from pathlib import Path
import time

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
job_id = os.environ["JOB_ID"]
report_key = f"{object_prefix}/reports/email_report.json"

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()
for queue in [
    os.environ["COMMAND_QUEUE"],
    os.environ["EVENT_COMPLETED_QUEUE"],
    os.environ["EVENT_FAILED_QUEUE"],
]:
    channel.queue_declare(queue=queue, durable=True)

command = {
    "job_id": job_id,
    "stage": "email_send",
}
channel.basic_publish(
    exchange="",
    routing_key=os.environ["COMMAND_QUEUE"],
    body=json.dumps(command, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
)

completed = None
failed = None
deadline = time.time() + 90
while time.time() < deadline:
    method, props, body = channel.basic_get(os.environ["EVENT_FAILED_QUEUE"], auto_ack=True)
    if method is not None:
        failed = json.loads(body.decode("utf-8"))
        break
    method, props, body = channel.basic_get(os.environ["EVENT_COMPLETED_QUEUE"], auto_ack=True)
    if method is not None:
        event = json.loads(body.decode("utf-8"))
        if event.get("job_id") == job_id:
            completed = event
            break
    time.sleep(1)

connection.close()
if failed:
    raise SystemExit(f"received failed event: {json.dumps(failed, sort_keys=True)}")
if not completed:
    raise SystemExit("timed out waiting for email_send stage.completed event")
if completed.get("outputs") != {"email_report": report_key}:
    raise SystemExit(f"unexpected outputs: {json.dumps(completed, sort_keys=True)}")
print(json.dumps(completed, sort_keys=True))

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
out = Path("/work/out")
report_path = out / "email_report.json"
client.fget_object(bucket, report_key, str(report_path))
report = json.loads(report_path.read_text(encoding="utf-8"))
if report.get("provider") != "mock" or report.get("status") != "sent":
    raise SystemExit(f"unexpected email report: {report!r}")
if report.get("attachments") != [
    f"{object_prefix}/05_export/final.docx",
    f"{object_prefix}/05_export/final.pdf",
    f"{object_prefix}/06_hwpx/final.hwpx",
]:
    raise SystemExit(f"unexpected attachments: {report!r}")
if "token" in json.dumps(report).lower() or "password" in json.dumps(report).lower():
    raise SystemExit(f"report contains secret-like field: {report!r}")
PY

pass "email-worker live smoke completed"
