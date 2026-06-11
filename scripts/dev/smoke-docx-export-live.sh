#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-docx-export-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-export-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-export-rabbitmq-live}"
WORKER_CONTAINER="${WORKER_CONTAINER:-ft-docx-export-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-docx-export-seed-live}"
PUBLISH_CONTAINER="${PUBLISH_CONTAINER:-ft-docx-export-publish-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
WORKER_IMAGE="${WORKER_IMAGE:-petoo/file-translation-libreoffice-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"

OBJECT_PREFIX="${OBJECT_PREFIX:-2026-01-21/12345678/exportsmoke1}"
JOB_ID="${JOB_ID:-live-docx-export-smoke}"
OUT_DIR="${OUT_DIR:-out/docx-export-live}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUE="${COMMAND_QUEUE:-q.commands.docx_export}"
EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-docx-export-live.sh

Runs a Docker-based live smoke for:
  RabbitMQ command -> libreoffice-worker docx_export -> MinIO final DOCX/PDF -> RabbitMQ event

Environment variables:
  NETWORK                 Docker network. Default: ft-docx-export-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  WORKER_IMAGE            Default: petoo/file-translation-libreoffice-worker:0.1.0
  MINIO_ACCESS_KEY        Default: minioadmin
  MINIO_SECRET_KEY        Default: minioadmin
  RABBITMQ_USERNAME       Default: guest
  RABBITMQ_PASSWORD       Default: guest
  MINIO_BUCKET            Default: file-translation
  OBJECT_PREFIX           Default: 2026-01-21/12345678/exportsmoke1
  JOB_ID                  Default: live-docx-export-smoke
  OUT_DIR                 Default: out/docx-export-live
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
    docker logs "$WORKER_CONTAINER" >/tmp/docx-export-worker-live.log 2>&1 || true
    if [ -s /tmp/docx-export-worker-live.log ]; then
      printf '[INFO] worker logs:\n' >&2
      cat /tmp/docx-export-worker-live.log >&2
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

note "Creating sample translated DOCX"
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
    "<w:r><w:t>[ko] Hello world</w:t></w:r>"
    "<w:r><w:t>[ko] Translate me</w:t></w:r>"
    "</w:p></w:body></w:document>"
)
with zipfile.ZipFile(out / "translated.docx", "w") as archive:
    archive.writestr("word/document.xml", document_xml)
PY

note "Waiting for MinIO/RabbitMQ and seeding translated DOCX"
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
            f"{object_prefix}/04_replace/translated.docx",
            "/work/out/translated.docx",
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

note "Starting libreoffice-worker docx_export consumer"
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
  -e "DOCX_EXPORT_PDF_MODE=placeholder" \
  "$WORKER_IMAGE" \
  python /app/service/worker.py --consume >/dev/null

note "Publishing docx_export command and waiting for completed event"
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
import xml.etree.ElementTree as ET

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
    "stage": "docx_export",
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
    raise SystemExit("timed out waiting for docx_export stage.completed event")

expected_outputs = {
    "final_docx": f"{object_prefix}/05_export/final.docx",
    "final_pdf": f"{object_prefix}/05_export/final.pdf",
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
final_docx = out / "final.docx"
final_pdf = out / "final.pdf"
client.fget_object(bucket, expected_outputs["final_docx"], str(final_docx))
client.fget_object(bucket, expected_outputs["final_pdf"], str(final_pdf))

with zipfile.ZipFile(final_docx, "r") as archive:
    root = ET.fromstring(archive.read("word/document.xml"))
texts = [
    node.text or ""
    for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
]
if texts != ["[ko] Hello world", "[ko] Translate me"]:
    raise SystemExit(f"unexpected final DOCX texts: {texts!r}")
if not final_pdf.read_bytes().startswith(b"%PDF-1.4"):
    raise SystemExit("final PDF does not look like the placeholder PDF")
PY

pass "docx_export live smoke completed"
