#!/usr/bin/env bash
set -Eeuo pipefail

DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"

NETWORK="${NETWORK:-ft-email-end-state-live}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-email-end-state-minio-live}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-email-end-state-rabbitmq-live}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-ft-email-end-state-postgres-live}"
JOB_SERVICE_CONTAINER="${JOB_SERVICE_CONTAINER:-ft-email-end-state-job-service-live}"
EMAIL_WORKER_CONTAINER="${EMAIL_WORKER_CONTAINER:-ft-email-end-state-worker-live}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-email-end-state-seed-live}"
DRIVER_CONTAINER="${DRIVER_CONTAINER:-ft-email-end-state-driver-live}"
DB_CHECK_CONTAINER="${DB_CHECK_CONTAINER:-ft-email-end-state-db-check-live}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
JOB_SERVICE_IMAGE="${JOB_SERVICE_IMAGE:-${DOCKER_NAMESPACE}/file-translation-job-service:${IMAGE_TAG}}"
EMAIL_WORKER_IMAGE="${EMAIL_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-email-worker:${IMAGE_TAG}}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
POSTGRES_USER="${POSTGRES_USER:-file_translation}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-file_translation}"
POSTGRES_DB="${POSTGRES_DB:-file_translation}"

OUT_DIR="${OUT_DIR:-out/email-end-state-live}"
USER_ID="${USER_ID:-12345678}"
FILE_ID="${FILE_ID:-emailendstatehwpx}"
INPUT_KEY="${INPUT_KEY:-2026-01-21/${USER_ID}/${FILE_ID}/input/original.hwpx}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-email-end-state-live.sh

Runs a Docker-based live smoke for:
  job-service/PostgreSQL/RabbitMQ sendability -> email-worker mock send ->
  MinIO email_report.json -> job-service terminal completed state

This smoke intentionally uses synthetic upstream stage.completed events. The HWPX
worker artifact path is covered by smoke-hwpx-replace-export-live.sh; this script
focuses on the email_send sendability and end-state contract.

Environment variables:
  DOCKER_NAMESPACE       Default: petoo
  IMAGE_TAG              Default: 0.1.0
  MINIO_IMAGE            Default: minio/minio:RELEASE.2025-02-07T23-21-09Z
  RABBITMQ_IMAGE         Default: rabbitmq:3.13-management
  POSTGRES_IMAGE         Default: postgres:16-alpine
  JOB_SERVICE_IMAGE      Default: $DOCKER_NAMESPACE/file-translation-job-service:$IMAGE_TAG
  EMAIL_WORKER_IMAGE     Default: $DOCKER_NAMESPACE/file-translation-email-worker:$IMAGE_TAG
  OUT_DIR                Default: out/email-end-state-live
  KEEP_LIVE_SMOKE=1      Keep containers/network after the smoke.
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
    for container in "$JOB_SERVICE_CONTAINER" "$EMAIL_WORKER_CONTAINER"; do
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
      "$DRIVER_CONTAINER" \
      "$SEED_CONTAINER" \
      "$EMAIL_WORKER_CONTAINER" \
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
  "$DRIVER_CONTAINER" \
  "$SEED_CONTAINER" \
  "$EMAIL_WORKER_CONTAINER" \
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

note "Waiting for PostgreSQL DNS/connectivity from the smoke network"
docker run --rm -i \
  --network "$NETWORK" \
  -e "POSTGRES_HOST=postgres" \
  -e "POSTGRES_PORT=5432" \
  -e "POSTGRES_DB=${POSTGRES_DB}" \
  -e "POSTGRES_USER=${POSTGRES_USER}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  "$JOB_SERVICE_IMAGE" \
  python - <<'PY'
import os
import time

import psycopg

for attempt in range(60):
    try:
        with psycopg.connect(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
PY

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
  "$EMAIL_WORKER_IMAGE" \
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

note "Waiting for job-service readiness"
docker run --rm -i \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  "$EMAIL_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
import time
from urllib import error, request

base_url = os.environ["JOB_SERVICE_URL"].rstrip("/")
for attempt in range(180):
    try:
        with request.urlopen(f"{base_url}/readyz", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict):
            break
    except (OSError, error.URLError):
        if attempt == 179:
            raise
        time.sleep(1)
PY

note "Starting email-worker consumer"
docker run -d \
  --name "$EMAIL_WORKER_CONTAINER" \
  --network "$NETWORK" \
  --network-alias email-worker \
  -e "EMAIL_PROVIDER=mock" \
  -e "EMAIL_SEND_ENABLED=true" \
  -e "EMAIL_FROM=no-reply@example.local" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$EMAIL_WORKER_IMAGE" \
  python /app/service/worker.py --consume --work-dir /tmp/file-translation/email-worker >/dev/null

note "Driving route to email_send and verifying terminal completed state"
docker run --rm -i \
  --name "$DRIVER_CONTAINER" \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "POSTGRES_HOST=postgres" \
  -e "POSTGRES_PORT=5432" \
  -e "POSTGRES_DB=${POSTGRES_DB}" \
  -e "POSTGRES_USER=${POSTGRES_USER}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  -e "USER_ID=${USER_ID}" \
  -e "FILE_ID=${FILE_ID}" \
  -e "INPUT_KEY=${INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$EMAIL_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
import tempfile
import time
from pathlib import Path
from urllib import error, request

import pika
from minio import Minio

base_url = os.environ["JOB_SERVICE_URL"].rstrip("/")
bucket = os.environ["MINIO_BUCKET"]
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


def rabbit_channel():
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
    return connection, channel


def publish_completed(channel, *, job_id: str, input_type: str, stage: str, outputs: dict[str, str]) -> None:
    event = {
        "event_type": "stage.completed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "outputs": outputs,
    }
    channel.basic_publish(
        exchange="",
        routing_key="q.events.stage_completed",
        body=json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )


def wait_job(job_id: str, status: str, current_stage: str, timeout_seconds: int = 120) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    last: dict[str, object] | None = None
    while time.time() < deadline:
        last = http_json("GET", f"/jobs/{job_id}")
        if last.get("status") == "failed":
            raise AssertionError(f"job failed: {last}")
        if last.get("status") == status and last.get("current_stage") == current_stage:
            return last
        time.sleep(1)
    raise AssertionError(f"job did not reach {status}/{current_stage}: {last}")


def upload_bytes(client: Minio, key: str, payload: bytes, content_type: str) -> None:
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(payload)
        path = Path(handle.name)
    try:
        client.fput_object(bucket, key, str(path), content_type=content_type)
    finally:
        path.unlink(missing_ok=True)


wait_ready()
connection, channel = rabbit_channel()
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
    channel.queue_purge(queue=queue)

created = http_json(
    "POST",
    "/jobs",
    {
        "user_id": os.environ["USER_ID"],
        "input_type": "hwpx",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "email-end-state.hwpx",
        "file_id": os.environ["FILE_ID"],
        "input_object_key": os.environ["INPUT_KEY"],
    },
)
job = created["job"]
if not isinstance(job, dict):
    raise AssertionError(f"unexpected create response: {created}")
job_id = str(job["job_id"])
object_prefix = str(job["object_prefix"]).strip("/")
published_command = created["published_command"]
if not isinstance(published_command, dict) or published_command.get("input_object_key") != os.environ["INPUT_KEY"]:
    raise AssertionError(f"initial command did not carry input_object_key: {published_command}")

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
expected = {
    "text_units": f"{object_prefix}/02_extract/text_units.json",
    "translated_units": f"{object_prefix}/03_translate/translated_units.json",
    "translated_hwpx": f"{object_prefix}/04_replace/translated.hwpx",
    "final_docx": f"{object_prefix}/05_export/final.docx",
    "final_pdf": f"{object_prefix}/05_export/final.pdf",
    "final_hwpx": f"{object_prefix}/06_hwpx/final.hwpx",
    "email_report": f"{object_prefix}/reports/email_report.json",
}
upload_bytes(client, os.environ["INPUT_KEY"], b"placeholder hwpx input", "application/octet-stream")
upload_bytes(client, expected["final_docx"], b"placeholder docx attachment", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
upload_bytes(client, expected["final_pdf"], b"%PDF-1.4\n% placeholder\n", "application/pdf")
upload_bytes(client, expected["final_hwpx"], b"placeholder hwpx attachment", "application/octet-stream")
upload_bytes(client, expected["translated_hwpx"], b"placeholder translated hwpx attachment", "application/octet-stream")

channel.queue_purge("q.commands.hwpx_extract")
publish_completed(
    channel,
    job_id=job_id,
    input_type="hwpx",
    stage="hwpx_extract",
    outputs={"text_units": expected["text_units"]},
)
publish_completed(
    channel,
    job_id=job_id,
    input_type="hwpx",
    stage="hwpx_translate",
    outputs={"translated_units": expected["translated_units"]},
)
publish_completed(
    channel,
    job_id=job_id,
    input_type="hwpx",
    stage="hwpx_replace",
    outputs={"translated_hwpx": expected["translated_hwpx"]},
)
publish_completed(
    channel,
    job_id=job_id,
    input_type="hwpx",
    stage="hwpx_export",
    outputs={
        "final_docx": expected["final_docx"],
        "final_pdf": expected["final_pdf"],
        "final_hwpx": expected["final_hwpx"],
    },
)
connection.close()

completed_job = wait_job(job_id, "completed", "completed")
stages = completed_job.get("stages")
if not isinstance(stages, dict):
    raise AssertionError(f"job stages missing: {completed_job}")
for stage in ["hwpx_extract", "hwpx_translate", "hwpx_replace", "hwpx_export", "email_send"]:
    state = stages.get(stage)
    if not isinstance(state, dict) or state.get("status") != "completed":
        raise AssertionError(f"stage {stage} did not complete: {state}")
artifacts = completed_job.get("artifacts")
if not isinstance(artifacts, dict):
    raise AssertionError(f"job artifacts missing: {completed_job}")
for name, key in expected.items():
    if artifacts.get(name) != key:
        raise AssertionError(f"artifact {name} expected {key}, got {artifacts.get(name)}")

sendability_after = http_json("GET", f"/jobs/{job_id}/sendability")
if sendability_after.get("sendable") is not False:
    raise AssertionError(f"completed job should no longer be sendable: {sendability_after}")

report_path = Path("/work/out/email_report.json")
client.fget_object(bucket, expected["email_report"], str(report_path))
report = json.loads(report_path.read_text(encoding="utf-8"))
if report.get("provider") != "mock" or report.get("status") != "sent":
    raise AssertionError(f"unexpected email report status: {report}")
if report.get("provider_message_id") != f"mock-{job_id}":
    raise AssertionError(f"unexpected provider message id: {report}")
if report.get("attachments") != [
    expected["final_docx"],
    expected["final_pdf"],
    expected["final_hwpx"],
    expected["translated_hwpx"],
]:
    raise AssertionError(f"unexpected email attachments: {report}")
if "token" in json.dumps(report).lower() or "password" in json.dumps(report).lower():
    raise AssertionError(f"report contains secret-like field: {report}")

Path("/work/out/result.json").write_text(
    json.dumps(
        {
            "job_id": job_id,
            "object_prefix": object_prefix,
            "artifacts": expected,
            "sendability_after": sendability_after,
            "email_report": report,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps({"job_id": job_id, "status": "completed", "email_report": expected["email_report"]}, separators=(",", ":"), sort_keys=True))
PY

note "Checking PostgreSQL JSONB terminal state directly"
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
import os
from pathlib import Path

import psycopg

result = json.loads(Path("/work/out/result.json").read_text(encoding="utf-8"))
job_id = result["job_id"]
expected = result["artifacts"]

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
    raise AssertionError(f"unexpected PostgreSQL JSONB payload: {payload!r}")
if payload.get("status") != "completed" or payload.get("current_stage") != "completed":
    raise AssertionError(f"PostgreSQL payload is not completed: {payload}")
if payload.get("artifacts", {}).get("email_report") != expected["email_report"]:
    raise AssertionError(f"PostgreSQL email_report artifact missing: {payload}")
for stage in ["hwpx_extract", "hwpx_translate", "hwpx_replace", "hwpx_export", "email_send"]:
    state = payload.get("stages", {}).get(stage, {})
    if state.get("status") != "completed":
        raise AssertionError(f"PostgreSQL stage {stage} did not complete: {state}")
print(json.dumps({"job_id": job_id, "postgres": "completed"}, separators=(",", ":"), sort_keys=True))
PY

pass "email_send end-state live smoke completed"
