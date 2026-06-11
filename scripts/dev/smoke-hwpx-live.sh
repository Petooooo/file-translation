#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-hwpx-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-hwpx-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-hwpx-rabbitmq-live}"
HWPX_WORKER_CONTAINER="${HWPX_WORKER_CONTAINER:-ft-hwpx-worker-live}"
TRANSLATE_WORKER_CONTAINER="${TRANSLATE_WORKER_CONTAINER:-ft-hwpx-translate-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-hwpx-seed-live}"
PUBLISH_CONTAINER="${PUBLISH_CONTAINER:-ft-hwpx-publish-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
HWPX_WORKER_IMAGE="${HWPX_WORKER_IMAGE:-petoo/file-translation-hwpx-worker:0.1.0}"
TRANSLATE_WORKER_IMAGE="${TRANSLATE_WORKER_IMAGE:-petoo/file-translation-translate-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"

OBJECT_PREFIX="${OBJECT_PREFIX:-2026-01-21/12345678/hwpxlivesmoke1}"
JOB_ID="${JOB_ID:-live-hwpx-smoke}"
OUT_DIR="${OUT_DIR:-out/hwpx-live}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

EXTRACT_COMMAND_QUEUE="${EXTRACT_COMMAND_QUEUE:-q.commands.hwpx_extract}"
TRANSLATE_COMMAND_QUEUE="${TRANSLATE_COMMAND_QUEUE:-q.commands.hwpx_translate}"
EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"
EVENT_PROGRESS_QUEUE="${EVENT_PROGRESS_QUEUE:-q.events.progress}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-hwpx-live.sh

Runs a Docker-based live smoke for:
  MinIO input HWPX -> RabbitMQ hwpx_extract -> hwpx-worker text_units.json
  RabbitMQ hwpx_translate -> translate-worker translated_units.json

Environment variables:
  NETWORK                 Docker network. Default: ft-hwpx-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  HWPX_WORKER_IMAGE       Default: petoo/file-translation-hwpx-worker:0.1.0
  TRANSLATE_WORKER_IMAGE  Default: petoo/file-translation-translate-worker:0.1.0
  MINIO_ACCESS_KEY        Default: minioadmin
  MINIO_SECRET_KEY        Default: minioadmin
  RABBITMQ_USERNAME       Default: guest
  RABBITMQ_PASSWORD       Default: guest
  MINIO_BUCKET            Default: file-translation
  OBJECT_PREFIX           Default: 2026-01-21/12345678/hwpxlivesmoke1
  JOB_ID                  Default: live-hwpx-smoke
  OUT_DIR                 Default: out/hwpx-live
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
    docker logs "$HWPX_WORKER_CONTAINER" >/tmp/hwpx-worker-live.log 2>&1 || true
    if [ -s /tmp/hwpx-worker-live.log ]; then
      printf '[INFO] hwpx-worker logs:\n' >&2
      cat /tmp/hwpx-worker-live.log >&2
    fi
    docker logs "$TRANSLATE_WORKER_CONTAINER" >/tmp/hwpx-translate-worker-live.log 2>&1 || true
    if [ -s /tmp/hwpx-translate-worker-live.log ]; then
      printf '[INFO] translate-worker logs:\n' >&2
      cat /tmp/hwpx-translate-worker-live.log >&2
    fi
  fi
  if [ "$KEEP_LIVE_SMOKE" != "1" ]; then
    docker rm -f \
      "$PUBLISH_CONTAINER" \
      "$SEED_CONTAINER" \
      "$TRANSLATE_WORKER_CONTAINER" \
      "$HWPX_WORKER_CONTAINER" \
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
  "$TRANSLATE_WORKER_CONTAINER" \
  "$HWPX_WORKER_CONTAINER" \
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

note "Creating sample HWPX"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
docker run --rm -i \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$HWPX_WORKER_IMAGE" \
  python /app/service/worker.py \
    --create-sample-local \
    --output /work/out/original.hwpx \
    --sample-text "Hello world" \
    --sample-text "Translate me" >/dev/null

note "Waiting for MinIO/RabbitMQ and seeding HWPX input"
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
  -e "EXTRACT_COMMAND_QUEUE=${EXTRACT_COMMAND_QUEUE}" \
  -e "TRANSLATE_COMMAND_QUEUE=${TRANSLATE_COMMAND_QUEUE}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  -e "EVENT_PROGRESS_QUEUE=${EVENT_PROGRESS_QUEUE}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$HWPX_WORKER_IMAGE" \
  python - <<'PY'
import os
from pathlib import Path
import time

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
input_key = f"{object_prefix}/input/original.hwpx"
sample_hwpx = Path("/work/out/original.hwpx")

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
        minio_client.fput_object(bucket, input_key, str(sample_hwpx), content_type="application/octet-stream")
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
            os.environ["EXTRACT_COMMAND_QUEUE"],
            os.environ["TRANSLATE_COMMAND_QUEUE"],
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

note "Starting hwpx-worker extract consumer"
docker run -d \
  --name "$HWPX_WORKER_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$HWPX_WORKER_IMAGE" python /app/service/worker.py --consume-extract >/dev/null

note "Starting translate-worker HWPX consumer"
docker run -d \
  --name "$TRANSLATE_WORKER_CONTAINER" \
  --network "$NETWORK" \
  -e "TRANSLATION_PROVIDER=mock" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$TRANSLATE_WORKER_IMAGE" python /app/service/worker.py --consume-hwpx >/dev/null

note "Publishing hwpx_extract and hwpx_translate commands"
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
  -e "EXTRACT_COMMAND_QUEUE=${EXTRACT_COMMAND_QUEUE}" \
  -e "TRANSLATE_COMMAND_QUEUE=${TRANSLATE_COMMAND_QUEUE}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  -e "EVENT_PROGRESS_QUEUE=${EVENT_PROGRESS_QUEUE}" \
  "$HWPX_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
from pathlib import Path
import time

import pika
from minio import Minio

object_prefix = os.environ["OBJECT_PREFIX"].strip("/")
bucket = os.environ["MINIO_BUCKET"]
job_id = os.environ["JOB_ID"]
text_units_key = f"{object_prefix}/02_extract/text_units.json"
translated_units_key = f"{object_prefix}/03_translate/translated_units.json"

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()
for queue in [
    os.environ["EXTRACT_COMMAND_QUEUE"],
    os.environ["TRANSLATE_COMMAND_QUEUE"],
    os.environ["EVENT_COMPLETED_QUEUE"],
    os.environ["EVENT_FAILED_QUEUE"],
    os.environ["EVENT_PROGRESS_QUEUE"],
]:
    channel.queue_declare(queue=queue, durable=True)


def publish(queue_name: str, command: dict[str, object]) -> None:
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(command, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )


def wait_for_completed(stage: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    deadline = time.time() + 120
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
            event = json.loads(body.decode("utf-8"))
            if event.get("event_type") != "stage.completed":
                raise SystemExit(f"expected stage.completed, got {event}")
            if event.get("stage") != stage:
                raise SystemExit(f"expected stage {stage}, got {event}")
            return event, progress_events
        time.sleep(1)
    raise SystemExit(f"timed out waiting for {stage} stage.completed")


publish(
    os.environ["EXTRACT_COMMAND_QUEUE"],
    {
        "job_id": job_id,
        "input_type": "hwpx",
        "stage": "hwpx_extract",
        "attempt": 1,
        "object_prefix": object_prefix,
        "source_lang": "en",
        "target_lang": "ko",
    },
)
extract_event, _ = wait_for_completed("hwpx_extract")

minio_client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
text_units_path = Path("/tmp/hwpx_text_units.json")
minio_client.fget_object(bucket, text_units_key, str(text_units_path))
text_units = json.loads(text_units_path.read_text(encoding="utf-8"))
if text_units.get("schema_version") != "1.0":
    raise SystemExit(f"unexpected text_units schema: {text_units}")
if text_units.get("input_type") != "hwpx":
    raise SystemExit(f"unexpected text_units input_type: {text_units}")
if [unit.get("text") for unit in text_units.get("units", [])] != ["Hello world", "Translate me"]:
    raise SystemExit(f"unexpected text units: {text_units}")
if extract_event.get("outputs", {}).get("text_units") != text_units_key:
    raise SystemExit(f"unexpected extract outputs: {extract_event}")

publish(
    os.environ["TRANSLATE_COMMAND_QUEUE"],
    {
        "job_id": job_id,
        "input_type": "hwpx",
        "stage": "hwpx_translate",
        "attempt": 1,
        "object_prefix": object_prefix,
        "source_lang": "en",
        "target_lang": "ko",
    },
)
translate_event, progress_events = wait_for_completed("hwpx_translate")
if not progress_events:
    raise SystemExit("expected at least one translate.progress event")

translated_units_path = Path("/tmp/hwpx_translated_units.json")
minio_client.fget_object(bucket, translated_units_key, str(translated_units_path))
translated_units = json.loads(translated_units_path.read_text(encoding="utf-8"))
if translated_units.get("schema_version") != "1.0":
    raise SystemExit(f"unexpected translated_units schema: {translated_units}")
if translated_units.get("input_type") != "hwpx":
    raise SystemExit(f"unexpected translated_units input_type: {translated_units}")
if translated_units.get("provider") != "mock":
    raise SystemExit(f"unexpected translation provider: {translated_units}")
if [unit.get("translated") for unit in translated_units.get("units", [])] != [
    "[ko] Hello world",
    "[ko] Translate me",
]:
    raise SystemExit(f"unexpected translations: {translated_units}")
if translate_event.get("outputs", {}).get("translated_units") != translated_units_key:
    raise SystemExit(f"unexpected translate outputs: {translate_event}")

connection.close()
print(
    json.dumps(
        {
            "extract": extract_event,
            "translate": translate_event,
            "progress_count": len(progress_events),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY

pass "hwpx live smoke completed"
