#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-docx-replace-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-replace-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-replace-rabbitmq-live}"
WORKER_CONTAINER="${WORKER_CONTAINER:-ft-docx-replace-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-docx-replace-seed-live}"
PUBLISH_CONTAINER="${PUBLISH_CONTAINER:-ft-docx-replace-publish-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
WORKER_IMAGE="${WORKER_IMAGE:-petoo/file-translation-docx-replace-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"

OBJECT_PREFIX="${OBJECT_PREFIX:-2026-01-21/12345678/replacesmoke1}"
JOB_ID="${JOB_ID:-live-docx-replace-smoke}"
OUT_DIR="${OUT_DIR:-out/docx-replace-live}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUE="${COMMAND_QUEUE:-q.commands.docx_replace}"
EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-docx-replace-live.sh

Runs a Docker-based live smoke for:
  RabbitMQ command -> docx-replace-worker -> MinIO translated DOCX -> RabbitMQ event

Environment variables:
  NETWORK                 Docker network. Default: ft-docx-replace-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  WORKER_IMAGE            Default: petoo/file-translation-docx-replace-worker:0.1.0
  MINIO_ACCESS_KEY        Default: minioadmin
  MINIO_SECRET_KEY        Default: minioadmin
  RABBITMQ_USERNAME       Default: guest
  RABBITMQ_PASSWORD       Default: guest
  MINIO_BUCKET            Default: file-translation
  OBJECT_PREFIX           Default: 2026-01-21/12345678/replacesmoke1
  JOB_ID                  Default: live-docx-replace-smoke
  OUT_DIR                 Default: out/docx-replace-live
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
    docker logs "$WORKER_CONTAINER" >/tmp/docx-replace-worker-live.log 2>&1 || true
    if [ -s /tmp/docx-replace-worker-live.log ]; then
      printf '[INFO] worker logs:\n' >&2
      cat /tmp/docx-replace-worker-live.log >&2
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

note "Creating sample DOCX/text units/translated units"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
docker run --rm -i \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$WORKER_IMAGE" \
  python - <<'PY'
from pathlib import Path
import json
import zipfile

out = Path("/work/out")
out.mkdir(parents=True, exist_ok=True)
document_xml = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p>"
    "<w:r><w:t>Hello world</w:t></w:r>"
    "<w:r><w:t>Translate me</w:t></w:r>"
    "</w:p></w:body></w:document>"
)
with zipfile.ZipFile(out / "input.docx", "w") as archive:
    archive.writestr("word/document.xml", document_xml)

text_units = {
    "schema_version": "1.0",
    "job_id": "live-docx-replace-smoke",
    "input_type": "docx",
    "source_lang": "en",
    "target_lang": "ko",
    "units": [
        {
            "uid": "unit-000001",
            "text": "Hello world",
            "location": {
                "type": "docx_run",
                "path": "word/document.xml",
                "paragraph_index": 0,
                "run_index": 0,
                "text_index": 0,
            },
        },
        {
            "uid": "unit-000002",
            "text": "Translate me",
            "location": {
                "type": "docx_run",
                "path": "word/document.xml",
                "paragraph_index": 0,
                "run_index": 1,
                "text_index": 0,
            },
        },
    ],
}
translated_units = {
    "schema_version": "1.0",
    "job_id": "live-docx-replace-smoke",
    "input_type": "docx",
    "source_lang": "en",
    "target_lang": "ko",
    "provider": "mock",
    "units": [
        {"uid": "unit-000001", "source": "Hello world", "translated": "[ko] Hello world", "status": "translated"},
        {"uid": "unit-000002", "source": "Translate me", "translated": "[ko] Translate me", "status": "translated"},
    ],
}
(out / "text_units.json").write_text(json.dumps(text_units, ensure_ascii=False), encoding="utf-8")
(out / "translated_units.json").write_text(json.dumps(translated_units, ensure_ascii=False), encoding="utf-8")
PY

note "Waiting for MinIO/RabbitMQ and seeding input objects"
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
from pathlib import Path

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
objects = [
    (f"{object_prefix}/input/original.docx", Path("/work/out/input.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    (f"{object_prefix}/02_extract/text_units.json", Path("/work/out/text_units.json"), "application/json"),
    (f"{object_prefix}/03_translate/translated_units.json", Path("/work/out/translated_units.json"), "application/json"),
]

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
for attempt in range(60):
    try:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
        for key, path, content_type in objects:
            minio_client.fput_object(bucket, key, str(path), content_type=content_type)
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
for attempt in range(60):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.environ["RABBITMQ_HOST"],
                credentials=credentials,
            )
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

print(f"seeded {len(objects)} objects under {bucket}/{object_prefix}")
PY

note "Starting docx-replace-worker consumer"
docker run -d \
  --name "$WORKER_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$WORKER_IMAGE" python /app/service/worker.py --consume >/dev/null

note "Publishing command and waiting for worker event"
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

DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{DOCX_NAMESPACE}}}t"

object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
bucket = os.environ["MINIO_BUCKET"]
translated_docx_key = f"{object_prefix}/04_replace/translated.docx"
command = {
    "job_id": os.environ["JOB_ID"],
    "input_type": "docx",
    "stage": "docx_replace",
    "attempt": 1,
    "object_prefix": object_prefix,
}

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.environ["RABBITMQ_HOST"],
        credentials=credentials,
    )
)
channel = connection.channel()
channel.queue_declare(queue=os.environ["COMMAND_QUEUE"], durable=True)
channel.queue_declare(queue=os.environ["EVENT_COMPLETED_QUEUE"], durable=True)
channel.queue_declare(queue=os.environ["EVENT_FAILED_QUEUE"], durable=True)
channel.basic_publish(
    exchange="",
    routing_key=os.environ["COMMAND_QUEUE"],
    body=json.dumps(command, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
)

deadline = time.time() + 120
event = None
event_queue = None
while time.time() < deadline:
    for queue in [os.environ["EVENT_FAILED_QUEUE"], os.environ["EVENT_COMPLETED_QUEUE"]]:
        method, properties, body = channel.basic_get(queue=queue, auto_ack=True)
        if method:
            event = json.loads(body.decode("utf-8"))
            event_queue = queue
            break
    if event:
        break
    time.sleep(1)

connection.close()
if event is None:
    raise SystemExit("timed out waiting for stage event")
if event.get("event_type") != "stage.completed":
    raise SystemExit(f"expected stage.completed, got {event_queue}: {event}")

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
download_path = Path("/tmp/translated.docx")
minio_client.fget_object(bucket, translated_docx_key, str(download_path))
with zipfile.ZipFile(download_path) as archive:
    root = ET.fromstring(archive.read("word/document.xml"))
texts = [node.text or "" for node in root.iter(W_T)]
if texts != ["[ko] Hello world", "[ko] Translate me"]:
    raise SystemExit(f"unexpected DOCX texts: {texts}")

print(json.dumps(event, separators=(",", ":"), sort_keys=True))
PY

pass "docx_replace live smoke completed"
