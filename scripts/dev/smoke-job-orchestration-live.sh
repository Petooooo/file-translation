#!/usr/bin/env bash
set -Eeuo pipefail

NETWORK="${NETWORK:-ft-job-orchestration-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-job-orchestration-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-job-orchestration-rabbitmq-live}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-ft-job-orchestration-postgres-live}"
JOB_SERVICE_CONTAINER="${JOB_SERVICE_CONTAINER:-ft-job-orchestration-service-live}"
MINIO_SEED_CONTAINER="${MINIO_SEED_CONTAINER:-ft-job-orchestration-minio-seed-live}"
DRIVER_CONTAINER="${DRIVER_CONTAINER:-ft-job-orchestration-driver-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
JOB_SERVICE_IMAGE="${JOB_SERVICE_IMAGE:-petoo/file-translation-job-service:0.1.0}"
MINIO_CLIENT_IMAGE="${MINIO_CLIENT_IMAGE:-petoo/file-translation-hwpx-worker:0.1.0}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
POSTGRES_USER="${POSTGRES_USER:-file_translation}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-file_translation}"
POSTGRES_DB="${POSTGRES_DB:-file_translation}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

EVENT_COMPLETED_QUEUE="${EVENT_COMPLETED_QUEUE:-q.events.stage_completed}"
EVENT_FAILED_QUEUE="${EVENT_FAILED_QUEUE:-q.events.stage_failed}"
EVENT_PROGRESS_QUEUE="${EVENT_PROGRESS_QUEUE:-q.events.progress}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-job-orchestration-live.sh

Runs a Docker-based live smoke for:
  RabbitMQ stage.completed event -> job-service -> PostgreSQL state update -> RabbitMQ next command

Environment variables:
  NETWORK                 Docker network. Default: ft-job-orchestration-live
  MINIO_IMAGE             Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE          Default: rabbitmq:3.13-management
  POSTGRES_IMAGE          Default: postgres:16-alpine
  JOB_SERVICE_IMAGE       Default: petoo/file-translation-job-service:0.1.0
  MINIO_CLIENT_IMAGE      Default: petoo/file-translation-hwpx-worker:0.1.0
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
    docker logs "$JOB_SERVICE_CONTAINER" >/tmp/job-orchestration-service-live.log 2>&1 || true
    if [ -s /tmp/job-orchestration-service-live.log ]; then
      printf '[INFO] job-service logs:\n' >&2
      cat /tmp/job-orchestration-service-live.log >&2
    fi
  fi
  if [ "$KEEP_LIVE_SMOKE" != "1" ]; then
    docker rm -f \
      "$DRIVER_CONTAINER" \
      "$MINIO_SEED_CONTAINER" \
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
  "$DRIVER_CONTAINER" \
  "$MINIO_SEED_CONTAINER" \
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

note "Waiting for MinIO and creating bucket"
docker run --rm -i \
  --name "$MINIO_SEED_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  "$MINIO_CLIENT_IMAGE" \
  python - <<'PY'
import os
import time

from minio import Minio

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
for attempt in range(60):
    try:
        if not client.bucket_exists(os.environ["MINIO_BUCKET"]):
            client.make_bucket(os.environ["MINIO_BUCKET"])
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
PY

note "Waiting for RabbitMQ"
docker run --rm -i \
  --network "$NETWORK" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  -e "EVENT_PROGRESS_QUEUE=${EVENT_PROGRESS_QUEUE}" \
  "$JOB_SERVICE_IMAGE" \
  python - <<'PY'
import os
import time

import pika

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
for attempt in range(60):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
        )
        channel = connection.channel()
        for queue in [
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

note "Running orchestration scenarios"
docker run --rm -i \
  --name "$DRIVER_CONTAINER" \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "POSTGRES_HOST=postgres" \
  -e "POSTGRES_PORT=5432" \
  -e "POSTGRES_DB=${POSTGRES_DB}" \
  -e "POSTGRES_USER=${POSTGRES_USER}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "EVENT_COMPLETED_QUEUE=${EVENT_COMPLETED_QUEUE}" \
  -e "EVENT_FAILED_QUEUE=${EVENT_FAILED_QUEUE}" \
  -e "EVENT_PROGRESS_QUEUE=${EVENT_PROGRESS_QUEUE}" \
  "$JOB_SERVICE_IMAGE" \
  python - <<'PY'
import json
import os
import time
from urllib import request

import pika
import psycopg

api_base = os.environ["JOB_SERVICE_URL"].rstrip("/")
event_completed_queue = os.environ["EVENT_COMPLETED_QUEUE"]
event_failed_queue = os.environ["EVENT_FAILED_QUEUE"]
event_progress_queue = os.environ["EVENT_PROGRESS_QUEUE"]

command_queues = {
    "pdf2docx": "q.commands.pdf2docx",
    "docx_extract": "q.commands.docx_extract",
    "docx_translate": "q.commands.docx_translate",
    "hwpx_extract": "q.commands.hwpx_extract",
    "hwpx_translate": "q.commands.hwpx_translate",
}


def api_json(method, path, payload=None):
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(f"{api_base}{path}", data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api():
    for attempt in range(60):
        try:
            payload = api_json("GET", "/readyz")
            if payload.get("status") == "ok":
                return
        except Exception:
            if attempt == 59:
                raise
            time.sleep(1)


def rabbit_channel():
    credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
    )
    channel = connection.channel()
    for queue in [
        *command_queues.values(),
        event_completed_queue,
        event_failed_queue,
        event_progress_queue,
    ]:
        channel.queue_declare(queue=queue, durable=True)
    return connection, channel


def postgres_payload(job_id):
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
    return row[0]


def purge(channel, *queues):
    for queue in queues:
        channel.queue_purge(queue=queue)


def publish_completed(channel, job_id, input_type, stage, outputs):
    event = {
        "event_type": "stage.completed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "outputs": outputs,
    }
    channel.basic_publish(
        exchange="",
        routing_key=event_completed_queue,
        body=json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )


def wait_for_command(channel, queue, *, job_id, expected_stage):
    deadline = time.time() + 60
    while time.time() < deadline:
        method, properties, body = channel.basic_get(queue=queue, auto_ack=True)
        if method:
            command = json.loads(body.decode("utf-8"))
            if command.get("job_id") != job_id:
                continue
            if command.get("stage") != expected_stage:
                raise AssertionError(f"unexpected command stage from {queue}: {command}")
            return command
        time.sleep(1)
    raise AssertionError(f"timed out waiting for {expected_stage} command on {queue}")


def assert_no_command(channel, queue, *, job_id, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        method, properties, body = channel.basic_get(queue=queue, auto_ack=True)
        if method:
            command = json.loads(body.decode("utf-8"))
            if command.get("job_id") == job_id:
                raise AssertionError(f"cancelled job published unexpected command: {command}")
        time.sleep(1)


def create_job(input_type, file_id):
    payload = {
        "user_id": "12345678",
        "input_type": input_type,
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": f"sample.{input_type}",
        "file_id": file_id,
    }
    response = api_json("POST", "/jobs", payload)
    return response["job"]


def wait_for_db_stage(job_id, *, current_stage, completed_stage):
    deadline = time.time() + 60
    while time.time() < deadline:
        payload = postgres_payload(job_id)
        if payload.get("current_stage") == current_stage:
            stage_state = payload["stages"][completed_stage]
            if stage_state.get("status") == "completed":
                return payload
        time.sleep(1)
    raise AssertionError(f"PostgreSQL did not reach current_stage={current_stage} for {job_id}")


wait_for_api()
time.sleep(2)
connection, channel = rabbit_channel()

results = []
scenarios = [
    {
        "name": "pdf",
        "input_type": "pdf",
        "file_id": "orchestrationpdf",
        "completed_stage": "pdf2docx",
        "next_stage": "docx_extract",
        "next_queue": command_queues["docx_extract"],
        "outputs": {"converted_docx": "2026-01-21/12345678/orchestrationpdf/01_pdf2docx/converted.docx"},
    },
    {
        "name": "docx",
        "input_type": "docx",
        "file_id": "orchestrationdocx",
        "completed_stage": "docx_extract",
        "next_stage": "docx_translate",
        "next_queue": command_queues["docx_translate"],
        "outputs": {"text_units": "2026-01-21/12345678/orchestrationdocx/02_extract/text_units.json"},
    },
    {
        "name": "hwpx",
        "input_type": "hwpx",
        "file_id": "orchestrationhwpx",
        "completed_stage": "hwpx_extract",
        "next_stage": "hwpx_translate",
        "next_queue": command_queues["hwpx_translate"],
        "outputs": {"text_units": "2026-01-21/12345678/orchestrationhwpx/02_extract/text_units.json"},
    },
]

for scenario in scenarios:
    purge(channel, scenario["next_queue"], event_completed_queue, event_failed_queue)
    job = create_job(scenario["input_type"], scenario["file_id"])
    publish_completed(
        channel,
        job["job_id"],
        scenario["input_type"],
        scenario["completed_stage"],
        scenario["outputs"],
    )
    command = wait_for_command(
        channel,
        scenario["next_queue"],
        job_id=job["job_id"],
        expected_stage=scenario["next_stage"],
    )
    db_payload = wait_for_db_stage(
        job["job_id"],
        current_stage=scenario["next_stage"],
        completed_stage=scenario["completed_stage"],
    )
    if command["object_prefix"] != db_payload["object_prefix"]:
        raise AssertionError(f"command/db object_prefix mismatch: {command} {db_payload}")
    results.append(
        {
            "input_type": scenario["input_type"],
            "completed_stage": scenario["completed_stage"],
            "next_stage": scenario["next_stage"],
            "next_queue": scenario["next_queue"],
            "db_current_stage": db_payload["current_stage"],
        }
    )

purge(channel, command_queues["docx_translate"], event_completed_queue, event_failed_queue)
cancel_job = create_job("docx", "orchestrationcancel")
api_json("POST", f"/jobs/{cancel_job['job_id']}/cancel")
publish_completed(
    channel,
    cancel_job["job_id"],
    "docx",
    "docx_extract",
    {"text_units": "2026-01-21/12345678/orchestrationcancel/02_extract/text_units.json"},
)

deadline = time.time() + 60
cancel_payload = None
while time.time() < deadline:
    payload = postgres_payload(cancel_job["job_id"])
    if payload.get("status") == "cancelled" and payload.get("current_stage") == "cancelled":
        cancel_payload = payload
        break
    time.sleep(1)
if cancel_payload is None:
    raise AssertionError("cancelled job was not persisted as cancelled")
assert_no_command(channel, command_queues["docx_translate"], job_id=cancel_job["job_id"])
results.append(
    {
        "input_type": "docx",
        "completed_stage": "docx_extract",
        "cancelled": True,
        "next_command_published": False,
        "db_current_stage": cancel_payload["current_stage"],
    }
)

connection.close()
print(json.dumps({"scenarios": results}, separators=(",", ":"), sort_keys=True))
PY

pass "job-service orchestration live smoke completed"
