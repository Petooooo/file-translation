#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-pdf2hwpx-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-pdf2hwpx-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-pdf2hwpx-rabbitmq-live}"
WORKER_CONTAINER="${WORKER_CONTAINER:-ft-pdf2hwpx-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-pdf2hwpx-seed-live}"
PUBLISH_CONTAINER="${PUBLISH_CONTAINER:-ft-pdf2hwpx-publish-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
WORKER_IMAGE="${WORKER_IMAGE:-petoo/file-translation-pdf2hwpx-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"

OBJECT_PREFIX="${OBJECT_PREFIX:-2026-01-21/12345678/hwpxsmoke1}"
JOB_ID="${JOB_ID:-live-pdf2hwpx-smoke}"
OUT_DIR="${OUT_DIR:-out/pdf2hwpx-live}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUE="${COMMAND_QUEUE:-q.commands.pdf2hwpx}"
EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-pdf2hwpx-live.sh

Runs a Docker-based live smoke for:
  RabbitMQ command -> pdf2hwpx-worker placeholder -> MinIO final HWPX -> RabbitMQ event

Environment variables:
  NETWORK                 Docker network. Default: ft-pdf2hwpx-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  WORKER_IMAGE            Default: petoo/file-translation-pdf2hwpx-worker:0.1.0
  MINIO_ACCESS_KEY        Default: minioadmin
  MINIO_SECRET_KEY        Default: minioadmin
  RABBITMQ_USERNAME       Default: guest
  RABBITMQ_PASSWORD       Default: guest
  MINIO_BUCKET            Default: file-translation
  OBJECT_PREFIX           Default: 2026-01-21/12345678/hwpxsmoke1
  JOB_ID                  Default: live-pdf2hwpx-smoke
  OUT_DIR                 Default: out/pdf2hwpx-live
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
    docker logs "$WORKER_CONTAINER" >/tmp/pdf2hwpx-worker-live.log 2>&1 || true
    if [ -s /tmp/pdf2hwpx-worker-live.log ]; then
      printf '[INFO] worker logs:\n' >&2
      cat /tmp/pdf2hwpx-worker-live.log >&2
    fi
  fi
  if [ "$KEEP_LIVE_SMOKE" != "1" ]; then
    docker rm -f "$PUBLISH_CONTAINER" "$SEED_CONTAINER" "$WORKER_CONTAINER" "$RABBITMQ_CONTAINER" "$MINIO_CONTAINER" >/dev/null 2>&1 || true
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
docker rm -f "$PUBLISH_CONTAINER" "$SEED_CONTAINER" "$WORKER_CONTAINER" "$RABBITMQ_CONTAINER" "$MINIO_CONTAINER" >/dev/null 2>&1 || true
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

note "Creating sample marker DOCX"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
docker run --rm -i \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$WORKER_IMAGE" \
  python - <<'PY'
from pathlib import Path
import zipfile

out = Path("/work/out")
out.mkdir(parents=True, exist_ok=True)
document_xml = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p>"
    "<w:r><w:t>[ko]¡Hello¡world</w:t></w:r>"
    "</w:p></w:body></w:document>"
)
with zipfile.ZipFile(out / "marker.docx", "w") as archive:
    archive.writestr("word/document.xml", document_xml)
PY

note "Waiting for MinIO/RabbitMQ and seeding marker DOCX"
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
  -e "OBJECT_PREFIX=${OBJECT_PREFIX}" \
  -e "COMMAND_QUEUE=${COMMAND_QUEUE}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$WORKER_IMAGE" \
  python - <<'PY'
import os
import time

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
object_prefix = os.environ["OBJECT_PREFIX"].strip("/")

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
        client.fput_object(
            bucket,
            f"{object_prefix}/05_export/marker.docx",
            "/work/out/marker.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
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
        connection.close()
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
PY

note "Starting pdf2hwpx-worker consumer"
docker run -d \
  --name "$WORKER_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$WORKER_IMAGE" \
  python /app/service/worker.py --consume >/dev/null

note "Publishing pdf2hwpx command and waiting for completed event"
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
import zipfile

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
job_id = os.environ["JOB_ID"]

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
    "input_type": "docx",
    "stage": "pdf2hwpx",
    "object_prefix": object_prefix,
}
channel.basic_publish(
    exchange="",
    routing_key=os.environ["COMMAND_QUEUE"],
    body=json.dumps(command, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
)

completed = None
failed = None
deadline = time.time() + 60
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
    raise SystemExit("timed out waiting for pdf2hwpx stage.completed event")

expected_outputs = {
    "final_hwpx": f"{object_prefix}/06_hwpx/final.hwpx",
}
if completed.get("outputs") != expected_outputs:
    raise SystemExit(f"unexpected outputs: {json.dumps(completed, sort_keys=True)}")
print(json.dumps(completed, sort_keys=True))

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
out = Path("/work/out")
final_hwpx = out / "final.hwpx"
client.fget_object(bucket, expected_outputs["final_hwpx"], str(final_hwpx))

with zipfile.ZipFile(final_hwpx, "r") as archive:
    names = set(archive.namelist())
    if names != {"mimetype", "placeholder.json", "source/marker.docx"}:
        raise SystemExit(f"unexpected HWPX placeholder files: {names!r}")
    metadata = json.loads(archive.read("placeholder.json").decode("utf-8"))
if metadata.get("stage") != "pdf2hwpx" or metadata.get("placeholder") is not True:
    raise SystemExit(f"unexpected placeholder metadata: {metadata!r}")
if metadata.get("job_id") != job_id:
    raise SystemExit(f"unexpected job_id in metadata: {metadata!r}")
PY

pass "pdf2hwpx live smoke completed"
