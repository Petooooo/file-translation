#!/usr/bin/env bash
set -Eeuo pipefail

DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"

NETWORK="${NETWORK:-ft-hwpx-replace-export-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-hwpx-replace-export-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-hwpx-replace-export-rabbitmq-live}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-ft-hwpx-replace-export-postgres-live}"
JOB_SERVICE_CONTAINER="${JOB_SERVICE_CONTAINER:-ft-hwpx-replace-export-job-service-live}"
HWPX_EXTRACT_CONTAINER="${HWPX_EXTRACT_CONTAINER:-ft-hwpx-replace-export-extract-live}"
HWPX_REPLACE_CONTAINER="${HWPX_REPLACE_CONTAINER:-ft-hwpx-replace-export-replace-live}"
TRANSLATE_CONTAINER="${TRANSLATE_CONTAINER:-ft-hwpx-replace-export-translate-live}"
EXPORT_CONTAINER="${EXPORT_CONTAINER:-ft-hwpx-replace-export-export-live}"
MINIO_SEED_CONTAINER="${MINIO_SEED_CONTAINER:-ft-hwpx-replace-export-seed-live}"
CANCEL_DRIVER_CONTAINER="${CANCEL_DRIVER_CONTAINER:-ft-hwpx-replace-export-cancel-live}"
FLOW_SETUP_CONTAINER="${FLOW_SETUP_CONTAINER:-ft-hwpx-replace-export-setup-live}"
FLOW_VERIFY_CONTAINER="${FLOW_VERIFY_CONTAINER:-ft-hwpx-replace-export-verify-live}"
DB_CHECK_CONTAINER="${DB_CHECK_CONTAINER:-ft-hwpx-replace-export-db-check-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
JOB_SERVICE_IMAGE="${JOB_SERVICE_IMAGE:-${DOCKER_NAMESPACE}/file-translation-job-service:${IMAGE_TAG}}"
HWPX_WORKER_IMAGE="${HWPX_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-hwpx-worker:${IMAGE_TAG}}"
TRANSLATE_WORKER_IMAGE="${TRANSLATE_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-translate-worker:${IMAGE_TAG}}"
LIBREOFFICE_WORKER_IMAGE="${LIBREOFFICE_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-libreoffice-worker:${IMAGE_TAG}}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
POSTGRES_USER="${POSTGRES_USER:-file_translation}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-file_translation}"
POSTGRES_DB="${POSTGRES_DB:-file_translation}"

OUT_DIR="${OUT_DIR:-out/hwpx-replace-export-live}"
USER_ID="${USER_ID:-12345678}"
FULL_FILE_ID="${FULL_FILE_ID:-hwpxreplaceexport}"
CANCEL_FILE_ID="${CANCEL_FILE_ID:-hwpxreplacecancel}"
FULL_INPUT_KEY="${FULL_INPUT_KEY:-2026-01-21/${USER_ID}/${FULL_FILE_ID}/input/original.hwpx}"
CANCEL_INPUT_KEY="${CANCEL_INPUT_KEY:-2026-01-21/${USER_ID}/${CANCEL_FILE_ID}/input/original.hwpx}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUES=(
  q.commands.hwpx_extract
  q.commands.hwpx_translate
  q.commands.hwpx_replace
  q.commands.hwpx_export
  q.commands.email_send
)
EVENT_QUEUES=(
  q.events.stage_completed
  q.events.stage_failed
  q.events.progress
)

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-hwpx-replace-export-live.sh

Runs a Docker-based live smoke for the placeholder HWPX route:
  job-service -> hwpx_extract -> hwpx_translate -> hwpx_replace -> hwpx_export

The smoke uses real RabbitMQ, MinIO, and PostgreSQL containers. It verifies that
workers publish only events and job-service publishes the next stage commands.

Environment variables:
  DOCKER_NAMESPACE         Default: petoo
  IMAGE_TAG                Default: 0.1.0
  MINIO_IMAGE              Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE           Default: rabbitmq:3.13-management
  POSTGRES_IMAGE           Default: postgres:16-alpine
  JOB_SERVICE_IMAGE        Default: $DOCKER_NAMESPACE/file-translation-job-service:$IMAGE_TAG
  HWPX_WORKER_IMAGE        Default: $DOCKER_NAMESPACE/file-translation-hwpx-worker:$IMAGE_TAG
  TRANSLATE_WORKER_IMAGE   Default: $DOCKER_NAMESPACE/file-translation-translate-worker:$IMAGE_TAG
  LIBREOFFICE_WORKER_IMAGE Default: $DOCKER_NAMESPACE/file-translation-libreoffice-worker:$IMAGE_TAG
  OUT_DIR                  Default: out/hwpx-replace-export-live
  KEEP_LIVE_SMOKE=1        Keep containers/network after the smoke.
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
    for container in \
      "$JOB_SERVICE_CONTAINER" \
      "$HWPX_EXTRACT_CONTAINER" \
      "$TRANSLATE_CONTAINER" \
      "$HWPX_REPLACE_CONTAINER" \
      "$EXPORT_CONTAINER"; do
      docker logs "$container" >/tmp/"${container}.log" 2>&1 || true
      if [ -s /tmp/"${container}.log" ]; then
        printf '[INFO] logs for %s:\n' "$container" >&2
        cat /tmp/"${container}.log" >&2
      fi
    done
  fi
  if [ "$KEEP_LIVE_SMOKE" != "1" ]; then
    docker rm -f \
      "$DB_CHECK_CONTAINER" \
      "$FLOW_VERIFY_CONTAINER" \
      "$FLOW_SETUP_CONTAINER" \
      "$CANCEL_DRIVER_CONTAINER" \
      "$MINIO_SEED_CONTAINER" \
      "$EXPORT_CONTAINER" \
      "$TRANSLATE_CONTAINER" \
      "$HWPX_REPLACE_CONTAINER" \
      "$HWPX_EXTRACT_CONTAINER" \
      "$JOB_SERVICE_CONTAINER" \
      "$POSTGRES_CONTAINER" \
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
  "$DB_CHECK_CONTAINER" \
  "$FLOW_VERIFY_CONTAINER" \
  "$FLOW_SETUP_CONTAINER" \
  "$CANCEL_DRIVER_CONTAINER" \
  "$MINIO_SEED_CONTAINER" \
  "$EXPORT_CONTAINER" \
  "$TRANSLATE_CONTAINER" \
  "$HWPX_REPLACE_CONTAINER" \
  "$HWPX_EXTRACT_CONTAINER" \
  "$JOB_SERVICE_CONTAINER" \
  "$POSTGRES_CONTAINER" \
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

note "Starting PostgreSQL ${POSTGRES_IMAGE}"
docker run -d \
  --name "$POSTGRES_CONTAINER" \
  --network "$NETWORK" \
  --network-alias postgres \
  -e "POSTGRES_USER=${POSTGRES_USER}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  -e "POSTGRES_DB=${POSTGRES_DB}" \
  "$POSTGRES_IMAGE" >/dev/null

note "Waiting for PostgreSQL"
postgres_ready=0
for _ in $(seq 1 60); do
  if docker exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    postgres_ready=1
    break
  fi
  sleep 1
done
if [ "$postgres_ready" != "1" ]; then
  die "PostgreSQL did not become ready"
fi

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

note "Waiting for MinIO/RabbitMQ, creating bucket, and seeding fixed input keys"
docker run --rm -i \
  --name "$MINIO_SEED_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "FULL_INPUT_KEY=${FULL_INPUT_KEY}" \
  -e "CANCEL_INPUT_KEY=${CANCEL_INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$HWPX_WORKER_IMAGE" \
  python - <<'PY'
import os
import time
from pathlib import Path

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
sample = Path("/work/out/original.hwpx")

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
        for key in [os.environ["FULL_INPUT_KEY"], os.environ["CANCEL_INPUT_KEY"]]:
            minio_client.fput_object(bucket, key, str(sample), content_type="application/octet-stream")
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
queues = [
    "q.commands.hwpx_extract",
    "q.commands.hwpx_translate",
    "q.commands.hwpx_replace",
    "q.commands.hwpx_export",
    "q.commands.email_send",
    "q.events.stage_completed",
    "q.events.stage_failed",
    "q.events.progress",
]
for attempt in range(60):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
        )
        channel = connection.channel()
        for queue in queues:
            channel.queue_declare(queue=queue, durable=True)
            channel.queue_purge(queue=queue)
        connection.close()
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
PY

note "Starting job-service with PostgreSQL repository and RabbitMQ orchestration"
docker run -d \
  --name "$JOB_SERVICE_CONTAINER" \
  --network "$NETWORK" \
  --network-alias job-service \
  -e "JOB_SERVICE_REPOSITORY=postgres" \
  -e "JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq" \
  -e "JOB_SERVICE_EVENT_CONSUMER=rabbitmq" \
  -e "POSTGRES_HOST=postgres" \
  -e "POSTGRES_PORT=5432" \
  -e "POSTGRES_DB=${POSTGRES_DB}" \
  -e "POSTGRES_USER=${POSTGRES_USER}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$JOB_SERVICE_IMAGE" \
  python /app/service/app.py --host 0.0.0.0 --port 8080 >/dev/null

note "Verifying cancel gate before workers start"
docker run --rm -i \
  --name "$CANCEL_DRIVER_CONTAINER" \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "USER_ID=${USER_ID}" \
  -e "CANCEL_FILE_ID=${CANCEL_FILE_ID}" \
  -e "CANCEL_INPUT_KEY=${CANCEL_INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$HWPX_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
import time
from pathlib import Path
from urllib import error, request

import pika

base_url = os.environ["JOB_SERVICE_URL"].rstrip("/")
credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])


def http_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with request.urlopen(req, timeout=5) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise AssertionError("HTTP response must be a JSON object")
    return decoded


def wait_ready() -> None:
    for attempt in range(60):
        try:
            http_json("GET", "/readyz")
            return
        except (OSError, error.URLError):
            if attempt == 59:
                raise
            time.sleep(1)


def open_channel():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
    )
    channel = connection.channel()
    for queue in [
        "q.commands.hwpx_extract",
        "q.commands.hwpx_translate",
        "q.events.stage_completed",
        "q.events.stage_failed",
        "q.events.progress",
    ]:
        channel.queue_declare(queue=queue, durable=True)
    return connection, channel


def wait_job(job_id: str, expected_status: str, expected_stage: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for _ in range(60):
        last = http_json("GET", f"/jobs/{job_id}")
        if last.get("status") == expected_status and last.get("current_stage") == expected_stage:
            return last
        time.sleep(1)
    raise AssertionError(f"job did not reach {expected_status}/{expected_stage}: {last}")


wait_ready()
connection, channel = open_channel()
for queue in ["q.commands.hwpx_extract", "q.commands.hwpx_translate", "q.events.stage_completed"]:
    channel.queue_purge(queue=queue)

created = http_json(
    "POST",
    "/jobs",
    {
        "user_id": os.environ["USER_ID"],
        "input_type": "hwpx",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "cancel.hwpx",
        "file_id": os.environ["CANCEL_FILE_ID"],
        "input_object_key": os.environ["CANCEL_INPUT_KEY"],
    },
)
job = created["job"]
if not isinstance(job, dict):
    raise AssertionError("create job payload missing job object")
job_id = str(job["job_id"])
command = created["published_command"]
if not isinstance(command, dict) or command.get("input_object_key") != os.environ["CANCEL_INPUT_KEY"]:
    raise AssertionError(f"initial command did not carry input_object_key: {command}")

http_json("POST", f"/jobs/{job_id}/cancel")
event = {
    "event_type": "stage.completed",
    "job_id": job_id,
    "input_type": "hwpx",
    "stage": "hwpx_extract",
    "outputs": {
        "text_units": f"{job['object_prefix']}/02_extract/text_units.json",
    },
}
channel.basic_publish(
    exchange="",
    routing_key="q.events.stage_completed",
    body=json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
)
cancelled = wait_job(job_id, "cancelled", "cancelled")

unexpected: list[dict[str, object]] = []
deadline = time.time() + 5
while time.time() < deadline:
    method, _properties, body = channel.basic_get("q.commands.hwpx_translate", auto_ack=True)
    if method is None:
        time.sleep(0.2)
        continue
    decoded = json.loads(body.decode("utf-8"))
    if isinstance(decoded, dict):
        unexpected.append(decoded)
if unexpected:
    raise AssertionError(f"cancelled job published unexpected hwpx_translate command: {unexpected}")

for queue in ["q.commands.hwpx_extract", "q.commands.hwpx_translate", "q.events.stage_completed"]:
    channel.queue_purge(queue=queue)
connection.close()

Path("/work/out/cancel-result.json").write_text(
    json.dumps({"job_id": job_id, "job": cancelled}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps({"cancel_job_id": job_id, "status": "cancelled"}, separators=(",", ":"), sort_keys=True))
PY

note "Creating live HWPX job and pre-seeding dynamic object_prefix input before workers start"
docker run --rm -i \
  --name "$FLOW_SETUP_CONTAINER" \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "USER_ID=${USER_ID}" \
  -e "FULL_FILE_ID=${FULL_FILE_ID}" \
  -e "FULL_INPUT_KEY=${FULL_INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$HWPX_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
import time
from pathlib import Path
from urllib import error, request

import pika
from minio import Minio

base_url = os.environ["JOB_SERVICE_URL"].rstrip("/")


def http_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with request.urlopen(req, timeout=5) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise AssertionError("HTTP response must be a JSON object")
    return decoded


def wait_ready() -> None:
    for attempt in range(60):
        try:
            http_json("GET", "/readyz")
            return
        except (OSError, error.URLError):
            if attempt == 59:
                raise
            time.sleep(1)


wait_ready()

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()
for queue in [
    "q.commands.hwpx_extract",
    "q.commands.hwpx_translate",
    "q.commands.hwpx_replace",
    "q.commands.hwpx_export",
    "q.commands.email_send",
    "q.events.stage_completed",
    "q.events.stage_failed",
    "q.events.progress",
]:
    channel.queue_declare(queue=queue, durable=True)
    channel.queue_purge(queue=queue)
connection.close()

created = http_json(
    "POST",
    "/jobs",
    {
        "user_id": os.environ["USER_ID"],
        "input_type": "hwpx",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "replace-export.hwpx",
        "file_id": os.environ["FULL_FILE_ID"],
        "input_object_key": os.environ["FULL_INPUT_KEY"],
    },
)
job = created["job"]
if not isinstance(job, dict):
    raise AssertionError("create job payload missing job object")
command = created["published_command"]
if not isinstance(command, dict) or command.get("input_object_key") != os.environ["FULL_INPUT_KEY"]:
    raise AssertionError(f"initial command did not carry input_object_key: {command}")

object_prefix = str(job["object_prefix"]).strip("/")
dynamic_input_key = f"{object_prefix}/input/original.hwpx"
client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
client.fput_object(
    os.environ["MINIO_BUCKET"],
    dynamic_input_key,
    "/work/out/original.hwpx",
    content_type="application/octet-stream",
)

result = {
    "job_id": job["job_id"],
    "object_prefix": object_prefix,
    "fixed_input_key": os.environ["FULL_INPUT_KEY"],
    "dynamic_input_key": dynamic_input_key,
}
Path("/work/out/flow-setup.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(result, separators=(",", ":"), sort_keys=True))
PY

note "Starting HWPX extract worker"
docker run -d \
  --name "$HWPX_EXTRACT_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$HWPX_WORKER_IMAGE" \
  python /app/service/worker.py --consume-extract --work-dir /tmp/file-translation/hwpx-extract >/dev/null

note "Starting translate worker for HWPX"
docker run -d \
  --name "$TRANSLATE_CONTAINER" \
  --network "$NETWORK" \
  -e "TRANSLATION_PROVIDER=mock" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$TRANSLATE_WORKER_IMAGE" \
  python /app/service/worker.py --consume-hwpx --work-dir /tmp/file-translation/hwpx-translate >/dev/null

note "Starting HWPX replace worker"
docker run -d \
  --name "$HWPX_REPLACE_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$HWPX_WORKER_IMAGE" \
  python /app/service/worker.py --consume-replace --work-dir /tmp/file-translation/hwpx-replace >/dev/null

note "Starting HWPX export worker"
docker run -d \
  --name "$EXPORT_CONTAINER" \
  --network "$NETWORK" \
  -e "HWPX_H2O_EXPORT_ENABLED=false" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$LIBREOFFICE_WORKER_IMAGE" \
  python /app/service/worker.py --consume-hwpx-export --work-dir /tmp/file-translation/hwpx-export >/dev/null

note "Waiting for full HWPX placeholder route and validating MinIO artifacts"
docker run --rm -i \
  --name "$FLOW_VERIFY_CONTAINER" \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$HWPX_WORKER_IMAGE" \
  python - <<'PY'
import io
import json
import os
import time
import zipfile
from pathlib import Path
from urllib import request

from minio import Minio

base_url = os.environ["JOB_SERVICE_URL"].rstrip("/")
setup = json.loads(Path("/work/out/flow-setup.json").read_text(encoding="utf-8"))
job_id = setup["job_id"]
object_prefix = setup["object_prefix"]
bucket = os.environ["MINIO_BUCKET"]


def http_json(method: str, path: str) -> dict[str, object]:
    req = request.Request(f"{base_url}{path}", method=method)
    with request.urlopen(req, timeout=5) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise AssertionError("HTTP response must be a JSON object")
    return decoded


def wait_route() -> dict[str, object]:
    last: dict[str, object] | None = None
    for _ in range(180):
        last = http_json("GET", f"/jobs/{job_id}")
        if last.get("status") == "failed":
            raise AssertionError(f"job failed: {last}")
        if last.get("status") == "running" and last.get("current_stage") == "email_send":
            stages = last.get("stages")
            if isinstance(stages, dict) and all(
                isinstance(stages.get(stage), dict) and stages[stage].get("status") == "completed"
                for stage in ["hwpx_extract", "hwpx_translate", "hwpx_replace", "hwpx_export"]
            ):
                return last
        time.sleep(1)
    raise AssertionError(f"job did not reach email_send after hwpx_export: {last}")


def get_object(key: str) -> bytes:
    response = client.get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def assert_zip_contains(key: str, member: str, expected: str) -> None:
    data = get_object(key)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text = archive.read(member).decode("utf-8")
    if expected not in text:
        raise AssertionError(f"{key}:{member} did not contain {expected!r}")


job = wait_route()
client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)

expected_keys = {
    "text_units": f"{object_prefix}/02_extract/text_units.json",
    "translated_units": f"{object_prefix}/03_translate/translated_units.json",
    "translated_hwpx": f"{object_prefix}/04_replace/translated.hwpx",
    "final_docx": f"{object_prefix}/05_export/final.docx",
    "final_pdf": f"{object_prefix}/05_export/final.pdf",
    "final_hwpx": f"{object_prefix}/06_hwpx/final.hwpx",
}

artifacts = job.get("artifacts")
if not isinstance(artifacts, dict):
    raise AssertionError(f"job artifacts missing: {job}")
for name, key in expected_keys.items():
    if artifacts.get(name) != key:
        raise AssertionError(f"job artifact {name} expected {key}, got {artifacts.get(name)}")
    client.stat_object(bucket, key)

if job.get("translated_hwpx_key") != expected_keys["translated_hwpx"]:
    raise AssertionError(f"translated_hwpx_key mismatch: {job.get('translated_hwpx_key')}")
if job.get("final_docx_key") != expected_keys["final_docx"]:
    raise AssertionError(f"final_docx_key mismatch: {job.get('final_docx_key')}")
if job.get("final_pdf_key") != expected_keys["final_pdf"]:
    raise AssertionError(f"final_pdf_key mismatch: {job.get('final_pdf_key')}")
if job.get("final_hwpx_key") != expected_keys["final_hwpx"]:
    raise AssertionError(f"final_hwpx_key mismatch: {job.get('final_hwpx_key')}")

text_units = json.loads(get_object(expected_keys["text_units"]).decode("utf-8"))
translated_units = json.loads(get_object(expected_keys["translated_units"]).decode("utf-8"))
if text_units.get("input_type") != "hwpx" or len(text_units.get("units", [])) != 2:
    raise AssertionError(f"unexpected text_units payload: {text_units}")
if translated_units.get("provider") != "mock":
    raise AssertionError(f"unexpected translated_units provider: {translated_units}")
translated_values = [str(unit.get("translated", "")) for unit in translated_units.get("units", [])]
if "[ko] Hello world" not in translated_values or "[ko] Translate me" not in translated_values:
    raise AssertionError(f"translated units missing mock translations: {translated_values}")

assert_zip_contains(expected_keys["translated_hwpx"], "Contents/section0.xml", "[ko] Hello world")
assert_zip_contains(expected_keys["final_hwpx"], "Contents/section0.xml", "[ko] Translate me")
assert_zip_contains(expected_keys["final_docx"], "word/document.xml", "File Translation placeholder DOCX")
final_pdf = get_object(expected_keys["final_pdf"])
if not final_pdf.startswith(b"%PDF"):
    raise AssertionError("final_pdf artifact is not a PDF placeholder")

sendability = http_json("GET", f"/jobs/{job_id}/sendability")
if sendability.get("sendable") is not True:
    raise AssertionError(f"job should be sendable after hwpx_export: {sendability}")

result = {
    **setup,
    "job": job,
    "expected_keys": expected_keys,
    "sendability": sendability,
}
Path("/work/out/flow-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"job_id": job_id, "current_stage": job["current_stage"], "artifacts": expected_keys}, separators=(",", ":"), sort_keys=True))
PY

note "Checking PostgreSQL JSONB state directly"
docker run --rm -i \
  --name "$DB_CHECK_CONTAINER" \
  --network "$NETWORK" \
  -e "POSTGRES_HOST=postgres" \
  -e "POSTGRES_PORT=5432" \
  -e "POSTGRES_DB=${POSTGRES_DB}" \
  -e "POSTGRES_USER=${POSTGRES_USER}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$JOB_SERVICE_IMAGE" \
  python - <<'PY'
import json
from pathlib import Path
import os

import psycopg

flow = json.loads(Path("/work/out/flow-result.json").read_text(encoding="utf-8"))
cancel = json.loads(Path("/work/out/cancel-result.json").read_text(encoding="utf-8"))


def fetch(job_id: str) -> dict[str, object]:
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
            row = cursor.fetchone()
    if row is None:
        raise AssertionError(f"missing PostgreSQL job row: {job_id}")
    payload = row[0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise AssertionError(f"unexpected JSONB payload for {job_id}: {payload!r}")
    return payload


flow_job = fetch(flow["job_id"])
cancel_job = fetch(cancel["job_id"])
if flow_job.get("current_stage") != "email_send":
    raise AssertionError(f"flow job current_stage mismatch: {flow_job}")
for stage in ["hwpx_extract", "hwpx_translate", "hwpx_replace", "hwpx_export"]:
    state = flow_job.get("stages", {}).get(stage, {})
    if state.get("status") != "completed":
        raise AssertionError(f"stage {stage} was not completed in PostgreSQL payload: {state}")
for key_name, object_key in flow["expected_keys"].items():
    if flow_job.get("artifacts", {}).get(key_name) != object_key:
        raise AssertionError(f"PostgreSQL artifact {key_name} mismatch: {flow_job.get('artifacts')}")
if cancel_job.get("status") != "cancelled" or cancel_job.get("current_stage") != "cancelled":
    raise AssertionError(f"cancel job was not persisted as cancelled: {cancel_job}")
print(json.dumps({"flow_job_id": flow["job_id"], "cancel_job_id": cancel["job_id"], "postgres": "ok"}, separators=(",", ":"), sort_keys=True))
PY

pass "HWPX replace/export live smoke completed"
