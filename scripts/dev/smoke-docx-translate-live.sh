#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-docx-translate-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-translate-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-translate-rabbitmq-live}"
WORKER_CONTAINER="${WORKER_CONTAINER:-ft-docx-translate-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-docx-translate-seed-live}"
PUBLISH_CONTAINER="${PUBLISH_CONTAINER:-ft-docx-translate-publish-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
WORKER_IMAGE="${WORKER_IMAGE:-petoo/file-translation-translate-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"

OBJECT_PREFIX="${OBJECT_PREFIX:-2026-01-21/12345678/translatesmoke1}"
JOB_ID="${JOB_ID:-live-docx-translate-smoke}"
OUT_DIR="${OUT_DIR:-out/docx-translate-live}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUE="${COMMAND_QUEUE:-q.commands.docx_translate}"
EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"
EVENT_PROGRESS_QUEUE="${EVENT_PROGRESS_QUEUE:-q.events.progress}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-docx-translate-live.sh

Runs a Docker-based live smoke for:
  RabbitMQ command -> translate-worker -> MinIO translated_units.json -> RabbitMQ events

Environment variables:
  NETWORK                 Docker network. Default: ft-docx-translate-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  WORKER_IMAGE            Default: petoo/file-translation-translate-worker:0.1.0
  MINIO_ACCESS_KEY        Default: minioadmin
  MINIO_SECRET_KEY        Default: minioadmin
  RABBITMQ_USERNAME       Default: guest
  RABBITMQ_PASSWORD       Default: guest
  MINIO_BUCKET            Default: file-translation
  OBJECT_PREFIX           Default: 2026-01-21/12345678/translatesmoke1
  JOB_ID                  Default: live-docx-translate-smoke
  OUT_DIR                 Default: out/docx-translate-live
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
    docker logs "$WORKER_CONTAINER" >/tmp/docx-translate-worker-live.log 2>&1 || true
    if [ -s /tmp/docx-translate-worker-live.log ]; then
      printf '[INFO] worker logs:\n' >&2
      cat /tmp/docx-translate-worker-live.log >&2
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

note "Creating sample text_units.json"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
docker run --rm -i \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$WORKER_IMAGE" \
  python - <<'PY'
from pathlib import Path
import json

payload = {
    "schema_version": "1.0",
    "job_id": "live-docx-translate-smoke",
    "input_type": "docx",
    "source_lang": "en",
    "target_lang": "ko",
    "units": [
        {
            "uid": "unit-000001",
            "text": "Hello world",
            "location": {"type": "docx_run", "path": "word/document.xml", "paragraph_index": 0, "run_index": 0},
        },
        {
            "uid": "unit-000002",
            "text": "Translate me",
            "location": {"type": "docx_run", "path": "word/document.xml", "paragraph_index": 0, "run_index": 1},
        },
    ],
}
out = Path("/work/out")
out.mkdir(parents=True, exist_ok=True)
(out / "text_units.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

note "Waiting for MinIO/RabbitMQ and seeding input object"
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
  -e "EVENT_PROGRESS_QUEUE=${EVENT_PROGRESS_QUEUE}" \
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
input_key = f"{object_prefix}/02_extract/text_units.json"
sample_json = Path("/work/out/text_units.json")

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
        minio_client.fput_object(bucket, input_key, str(sample_json), content_type="application/json")
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
            os.environ["EVENT_PROGRESS_QUEUE"],
        ]:
            channel.queue_declare(queue=queue, durable=True)
            channel.queue_purge(queue=queue)
        connection.close()
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)

print(f"seeded {bucket}/{input_key}")
PY

note "Starting translate-worker consumer"
docker run -d \
  --name "$WORKER_CONTAINER" \
  --network "$NETWORK" \
  -e "TRANSLATION_PROVIDER=mock" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$WORKER_IMAGE" python /app/service/worker.py --consume >/dev/null

note "Publishing command and waiting for worker events"
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
  -e "EVENT_PROGRESS_QUEUE=${EVENT_PROGRESS_QUEUE}" \
  "$WORKER_IMAGE" \
  python - <<'PY'
import json
import os
from pathlib import Path
import time

import pika
from minio import Minio

object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
bucket = os.environ["MINIO_BUCKET"]
translated_units_key = f"{object_prefix}/03_translate/translated_units.json"
command = {
    "job_id": os.environ["JOB_ID"],
    "input_type": "docx",
    "stage": "docx_translate",
    "attempt": 1,
    "object_prefix": object_prefix,
    "source_lang": "en",
    "target_lang": "ko",
}

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
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
    os.environ["EVENT_PROGRESS_QUEUE"],
]:
    channel.queue_declare(queue=queue, durable=True)
channel.basic_publish(
    exchange="",
    routing_key=os.environ["COMMAND_QUEUE"],
    body=json.dumps(command, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
)

deadline = time.time() + 120
completed_event = None
progress_events = []
while time.time() < deadline:
    method, properties, body = channel.basic_get(queue=os.environ["EVENT_FAILED_QUEUE"], auto_ack=True)
    if method:
        raise SystemExit(f"received failed event: {json.loads(body.decode('utf-8'))}")
    method, properties, body = channel.basic_get(queue=os.environ["EVENT_PROGRESS_QUEUE"], auto_ack=True)
    if method:
        progress_events.append(json.loads(body.decode("utf-8")))
    method, properties, body = channel.basic_get(queue=os.environ["EVENT_COMPLETED_QUEUE"], auto_ack=True)
    if method:
        completed_event = json.loads(body.decode("utf-8"))
        break
    time.sleep(1)

connection.close()
if completed_event is None:
    raise SystemExit("timed out waiting for stage.completed")
if completed_event.get("event_type") != "stage.completed":
    raise SystemExit(f"expected stage.completed, got {completed_event}")
if len(progress_events) < 1:
    raise SystemExit("expected at least one translate.progress event")

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
download_path = Path("/tmp/translated_units.json")
minio_client.fget_object(bucket, translated_units_key, str(download_path))
payload = json.loads(download_path.read_text(encoding="utf-8"))
if payload.get("provider") != "mock":
    raise SystemExit(f"unexpected provider: {payload}")
if [unit.get("translated") for unit in payload.get("units", [])] != ["[ko] Hello world", "[ko] Translate me"]:
    raise SystemExit(f"unexpected translations: {payload}")

print(json.dumps({"completed": completed_event, "progress_count": len(progress_events)}, separators=(",", ":"), sort_keys=True))
PY

pass "docx_translate live smoke completed"
