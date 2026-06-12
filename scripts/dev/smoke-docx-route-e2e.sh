#!/usr/bin/env bash
set -Eeuo pipefail

DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"

NETWORK="${NETWORK:-ft-docx-route-e2e}"
MINIO_CONTAINER="${MINIO_CONTAINER:-ft-docx-route-e2e-minio}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-ft-docx-route-e2e-rabbitmq}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-ft-docx-route-e2e-postgres}"
JOB_SERVICE_CONTAINER="${JOB_SERVICE_CONTAINER:-ft-docx-route-e2e-job-service}"
DOCX_EXTRACT_CONTAINER="${DOCX_EXTRACT_CONTAINER:-ft-docx-route-e2e-extract}"
TRANSLATE_CONTAINER="${TRANSLATE_CONTAINER:-ft-docx-route-e2e-translate}"
DOCX_REPLACE_CONTAINER="${DOCX_REPLACE_CONTAINER:-ft-docx-route-e2e-replace}"
DOCX_EXPORT_CONTAINER="${DOCX_EXPORT_CONTAINER:-ft-docx-route-e2e-export}"
DOCX_MARKER_CONTAINER="${DOCX_MARKER_CONTAINER:-ft-docx-route-e2e-marker}"
PDF2HWPX_CONTAINER="${PDF2HWPX_CONTAINER:-ft-docx-route-e2e-pdf2hwpx}"
EMAIL_CONTAINER="${EMAIL_CONTAINER:-ft-docx-route-e2e-email}"
SEED_CONTAINER="${SEED_CONTAINER:-ft-docx-route-e2e-seed}"
CANCEL_DRIVER_CONTAINER="${CANCEL_DRIVER_CONTAINER:-ft-docx-route-e2e-cancel}"
SETUP_DRIVER_CONTAINER="${SETUP_DRIVER_CONTAINER:-ft-docx-route-e2e-setup}"
VERIFY_DRIVER_CONTAINER="${VERIFY_DRIVER_CONTAINER:-ft-docx-route-e2e-verify}"
DB_CHECK_CONTAINER="${DB_CHECK_CONTAINER:-ft-docx-route-e2e-db-check}"

MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
JOB_SERVICE_IMAGE="${JOB_SERVICE_IMAGE:-${DOCKER_NAMESPACE}/file-translation-job-service:${IMAGE_TAG}}"
DOCX_EXTRACT_WORKER_IMAGE="${DOCX_EXTRACT_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-docx-extract-worker:${IMAGE_TAG}}"
TRANSLATE_WORKER_IMAGE="${TRANSLATE_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-translate-worker:${IMAGE_TAG}}"
DOCX_REPLACE_WORKER_IMAGE="${DOCX_REPLACE_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-docx-replace-worker:${IMAGE_TAG}}"
LIBREOFFICE_WORKER_IMAGE="${LIBREOFFICE_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-libreoffice-worker:${IMAGE_TAG}}"
PDF2HWPX_WORKER_IMAGE="${PDF2HWPX_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-pdf2hwpx-worker:${IMAGE_TAG}}"
EMAIL_WORKER_IMAGE="${EMAIL_WORKER_IMAGE:-${DOCKER_NAMESPACE}/file-translation-email-worker:${IMAGE_TAG}}"

MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
POSTGRES_USER="${POSTGRES_USER:-file_translation}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-file_translation}"
POSTGRES_DB="${POSTGRES_DB:-file_translation}"

OUT_DIR="${OUT_DIR:-out/docx-route-e2e}"
USER_ID="${USER_ID:-12345678}"
MAIN_FILE_ID="${MAIN_FILE_ID:-docxroutee2e}"
MID_CANCEL_FILE_ID="${MID_CANCEL_FILE_ID:-docxroutecancelmid}"
EMAIL_CANCEL_FILE_ID="${EMAIL_CANCEL_FILE_ID:-docxroutecancelemail}"
MAIN_INPUT_KEY="${MAIN_INPUT_KEY:-2026-01-21/${USER_ID}/${MAIN_FILE_ID}/input/original.docx}"
MID_CANCEL_INPUT_KEY="${MID_CANCEL_INPUT_KEY:-2026-01-21/${USER_ID}/${MID_CANCEL_FILE_ID}/input/original.docx}"
EMAIL_CANCEL_INPUT_KEY="${EMAIL_CANCEL_INPUT_KEY:-2026-01-21/${USER_ID}/${EMAIL_CANCEL_FILE_ID}/input/original.docx}"
DOCX_MARKER_TOKEN="${DOCX_MARKER_TOKEN:-¡}"
KEEP_LIVE_SMOKE="${KEEP_LIVE_SMOKE:-0}"

COMMAND_QUEUES=(
  q.commands.docx_extract
  q.commands.docx_translate
  q.commands.docx_replace
  q.commands.docx_export
  q.commands.docx_marker
  q.commands.pdf2hwpx
  q.commands.email_send
)
EVENT_QUEUES=(
  q.events.stage_completed
  q.events.stage_failed
  q.events.progress
)

usage() {
  cat <<'EOF'
Usage: scripts/dev/smoke-docx-route-e2e.sh

Runs a Docker-based route-level DOCX E2E smoke:
  job-service create DOCX job -> docx_extract -> docx_translate ->
  docx_replace -> docx_export -> docx_marker -> pdf2hwpx ->
  email_send -> completed

This smoke uses placeholder DOCX export PDF and placeholder pdf2hwpx output.
It does not enable real LibreOffice export, real pdf2hwpx conversion, real
email delivery, or Helm.
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

push_uptime_kuma() {
  if [ -z "${UPTIME_KUMA_PUSH_URL:-}" ]; then
    return 0
  fi
  if ! has_cmd curl; then
    note "Skipping Uptime Kuma push because curl is not available"
    return 0
  fi
  curl -fsS --max-time 10 "$UPTIME_KUMA_PUSH_URL" >/dev/null 2>&1 \
    || note "Uptime Kuma push failed; smoke result remains successful"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    for container in \
      "$JOB_SERVICE_CONTAINER" \
      "$DOCX_EXTRACT_CONTAINER" \
      "$TRANSLATE_CONTAINER" \
      "$DOCX_REPLACE_CONTAINER" \
      "$DOCX_EXPORT_CONTAINER" \
      "$DOCX_MARKER_CONTAINER" \
      "$PDF2HWPX_CONTAINER" \
      "$EMAIL_CONTAINER"; do
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
      "$VERIFY_DRIVER_CONTAINER" \
      "$SETUP_DRIVER_CONTAINER" \
      "$CANCEL_DRIVER_CONTAINER" \
      "$SEED_CONTAINER" \
      "$EMAIL_CONTAINER" \
      "$PDF2HWPX_CONTAINER" \
      "$DOCX_MARKER_CONTAINER" \
      "$DOCX_EXPORT_CONTAINER" \
      "$DOCX_REPLACE_CONTAINER" \
      "$TRANSLATE_CONTAINER" \
      "$DOCX_EXTRACT_CONTAINER" \
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
  "$VERIFY_DRIVER_CONTAINER" \
  "$SETUP_DRIVER_CONTAINER" \
  "$CANCEL_DRIVER_CONTAINER" \
  "$SEED_CONTAINER" \
  "$EMAIL_CONTAINER" \
  "$PDF2HWPX_CONTAINER" \
  "$DOCX_MARKER_CONTAINER" \
  "$DOCX_EXPORT_CONTAINER" \
  "$DOCX_REPLACE_CONTAINER" \
  "$TRANSLATE_CONTAINER" \
  "$DOCX_EXTRACT_CONTAINER" \
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

note "Creating sample DOCX"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
docker run --rm -i \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$DOCX_EXTRACT_WORKER_IMAGE" \
  python - <<'PY'
from pathlib import Path
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
with zipfile.ZipFile(out / "original.docx", "w") as archive:
    archive.writestr("word/document.xml", document_xml)
PY

note "Waiting for MinIO/RabbitMQ, creating bucket, and seeding fixed DOCX input keys"
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
  -e "MAIN_INPUT_KEY=${MAIN_INPUT_KEY}" \
  -e "MID_CANCEL_INPUT_KEY=${MID_CANCEL_INPUT_KEY}" \
  -e "EMAIL_CANCEL_INPUT_KEY=${EMAIL_CANCEL_INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$DOCX_EXTRACT_WORKER_IMAGE" \
  python - <<'PY'
import os
import time
from pathlib import Path

import pika
from minio import Minio

bucket = os.environ["MINIO_BUCKET"]
sample = Path("/work/out/original.docx")

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
for attempt in range(60):
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        for key in [
            os.environ["MAIN_INPUT_KEY"],
            os.environ["MID_CANCEL_INPUT_KEY"],
            os.environ["EMAIL_CANCEL_INPUT_KEY"],
        ]:
            client.fput_object(
                bucket,
                key,
                str(sample),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
queues = [
    "q.commands.docx_extract",
    "q.commands.docx_translate",
    "q.commands.docx_replace",
    "q.commands.docx_export",
    "q.commands.docx_marker",
    "q.commands.pdf2hwpx",
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

note "Verifying cancellation gates before workers start"
docker run --rm -i \
  --name "$CANCEL_DRIVER_CONTAINER" \
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
  -e "MID_CANCEL_FILE_ID=${MID_CANCEL_FILE_ID}" \
  -e "MID_CANCEL_INPUT_KEY=${MID_CANCEL_INPUT_KEY}" \
  -e "EMAIL_CANCEL_FILE_ID=${EMAIL_CANCEL_FILE_ID}" \
  -e "EMAIL_CANCEL_INPUT_KEY=${EMAIL_CANCEL_INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$EMAIL_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
import time
from pathlib import Path
from urllib import request

import pika
from minio import Minio
from minio.error import S3Error

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


def open_channel():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
    )
    channel = connection.channel()
    for queue in [
        "q.commands.docx_extract",
        "q.commands.docx_translate",
        "q.commands.docx_replace",
        "q.commands.docx_export",
        "q.commands.docx_marker",
        "q.commands.pdf2hwpx",
        "q.commands.email_send",
        "q.events.stage_completed",
        "q.events.stage_failed",
        "q.events.progress",
    ]:
        channel.queue_declare(queue=queue, durable=True)
    return connection, channel


def purge_all(channel) -> None:
    for queue in [
        "q.commands.docx_extract",
        "q.commands.docx_translate",
        "q.commands.docx_replace",
        "q.commands.docx_export",
        "q.commands.docx_marker",
        "q.commands.pdf2hwpx",
        "q.commands.email_send",
        "q.events.stage_completed",
        "q.events.stage_failed",
        "q.events.progress",
    ]:
        channel.queue_purge(queue=queue)


def publish_completed(channel, *, job_id: str, stage: str, object_prefix: str) -> None:
    outputs_by_stage = {
        "docx_extract": {"text_units": f"{object_prefix}/02_extract/text_units.json"},
        "docx_translate": {"translated_units": f"{object_prefix}/03_translate/translated_units.json"},
        "docx_replace": {"translated_docx": f"{object_prefix}/04_replace/translated.docx"},
        "docx_export": {
            "final_docx": f"{object_prefix}/05_export/final.docx",
            "final_pdf": f"{object_prefix}/05_export/final.pdf",
        },
        "docx_marker": {"marker_docx": f"{object_prefix}/05_export/marker.docx"},
        "pdf2hwpx": {"final_hwpx": f"{object_prefix}/06_hwpx/final.hwpx"},
    }
    event = {
        "event_type": "stage.completed",
        "job_id": job_id,
        "input_type": "docx",
        "stage": stage,
        "outputs": outputs_by_stage[stage],
    }
    channel.basic_publish(
        exchange="",
        routing_key="q.events.stage_completed",
        body=json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )


def wait_job(job_id: str, status: str, current_stage: str, timeout_seconds: int = 60) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    last: dict[str, object] | None = None
    while time.time() < deadline:
        last = http_json("GET", f"/jobs/{job_id}")
        if last.get("status") == status and last.get("current_stage") == current_stage:
            return last
        time.sleep(1)
    raise AssertionError(f"job did not reach {status}/{current_stage}: {last}")


def create_docx_job(file_id: str, input_key: str) -> dict[str, object]:
    created = http_json(
        "POST",
        "/jobs",
        {
            "user_id": os.environ["USER_ID"],
            "input_type": "docx",
            "source_lang": "en",
            "target_lang": "ko",
            "original_filename": f"{file_id}.docx",
            "file_id": file_id,
            "input_object_key": input_key,
        },
    )
    job = created["job"]
    if not isinstance(job, dict):
        raise AssertionError(f"unexpected create response: {created}")
    command = created["published_command"]
    if not isinstance(command, dict) or command.get("input_object_key") != input_key:
        raise AssertionError(f"initial command did not carry input_object_key: {command}")
    return job


connection, channel = open_channel()
purge_all(channel)

mid_job = create_docx_job(os.environ["MID_CANCEL_FILE_ID"], os.environ["MID_CANCEL_INPUT_KEY"])
mid_job_id = str(mid_job["job_id"])
mid_prefix = str(mid_job["object_prefix"]).strip("/")
http_json("POST", f"/jobs/{mid_job_id}/cancel")
publish_completed(channel, job_id=mid_job_id, stage="docx_extract", object_prefix=mid_prefix)
wait_job(mid_job_id, "cancelled", "cancelled")

unexpected_translate: list[dict[str, object]] = []
deadline = time.time() + 5
while time.time() < deadline:
    method, _props, body = channel.basic_get("q.commands.docx_translate", auto_ack=True)
    if method is None:
        time.sleep(0.2)
        continue
    decoded = json.loads(body.decode("utf-8"))
    if isinstance(decoded, dict):
        unexpected_translate.append(decoded)
if unexpected_translate:
    raise AssertionError(f"mid-route cancelled job published docx_translate: {unexpected_translate}")
purge_all(channel)

email_job = create_docx_job(os.environ["EMAIL_CANCEL_FILE_ID"], os.environ["EMAIL_CANCEL_INPUT_KEY"])
email_job_id = str(email_job["job_id"])
email_prefix = str(email_job["object_prefix"]).strip("/")
for stage in ["docx_extract", "docx_translate", "docx_replace", "docx_export", "docx_marker", "pdf2hwpx"]:
    publish_completed(channel, job_id=email_job_id, stage=stage, object_prefix=email_prefix)
wait_job(email_job_id, "running", "email_send")
http_json("POST", f"/jobs/{email_job_id}/cancel")
sendability = http_json("GET", f"/jobs/{email_job_id}/sendability")
if sendability.get("sendable") is not False:
    raise AssertionError(f"cancelled email-stage job should not be sendable: {sendability}")

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
report_key = f"{email_prefix}/reports/email_report.json"
try:
    client.stat_object(bucket, report_key)
except S3Error as exc:
    if exc.code not in {"NoSuchKey", "NoSuchObject"}:
        raise
else:
    raise AssertionError(f"cancelled email-stage job wrote unexpected email report: {report_key}")
purge_all(channel)
connection.close()

result = {
    "mid_cancel_job_id": mid_job_id,
    "email_cancel_job_id": email_job_id,
    "email_cancel_sendability": sendability,
}
Path("/work/out/cancel-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(result, separators=(",", ":"), sort_keys=True))
PY

note "Creating DOCX E2E job and pre-seeding dynamic object_prefix input"
docker run --rm -i \
  --name "$SETUP_DRIVER_CONTAINER" \
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
  -e "MAIN_FILE_ID=${MAIN_FILE_ID}" \
  -e "MAIN_INPUT_KEY=${MAIN_INPUT_KEY}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$EMAIL_WORKER_IMAGE" \
  python - <<'PY'
import json
import os
from pathlib import Path
from urllib import request

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


credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()
for queue in [
    "q.commands.docx_extract",
    "q.commands.docx_translate",
    "q.commands.docx_replace",
    "q.commands.docx_export",
    "q.commands.docx_marker",
    "q.commands.pdf2hwpx",
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
        "input_type": "docx",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "route-e2e.docx",
        "file_id": os.environ["MAIN_FILE_ID"],
        "input_object_key": os.environ["MAIN_INPUT_KEY"],
    },
)
job = created["job"]
if not isinstance(job, dict):
    raise AssertionError(f"create job payload missing job object: {created}")
command = created["published_command"]
if not isinstance(command, dict) or command.get("input_object_key") != os.environ["MAIN_INPUT_KEY"]:
    raise AssertionError(f"initial command did not carry input_object_key: {command}")

object_prefix = str(job["object_prefix"]).strip("/")
dynamic_input_key = f"{object_prefix}/input/original.docx"
client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
client.fput_object(
    os.environ["MINIO_BUCKET"],
    dynamic_input_key,
    "/work/out/original.docx",
    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
setup = {
    "job_id": job["job_id"],
    "object_prefix": object_prefix,
    "fixed_input_key": os.environ["MAIN_INPUT_KEY"],
    "dynamic_input_key": dynamic_input_key,
}
Path("/work/out/e2e-setup.json").write_text(json.dumps(setup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(setup, separators=(",", ":"), sort_keys=True))
PY

note "Starting DOCX extract worker"
docker run -d \
  --name "$DOCX_EXTRACT_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$DOCX_EXTRACT_WORKER_IMAGE" \
  python /app/service/worker.py --consume --work-dir /tmp/file-translation/docx-extract >/dev/null

note "Starting DOCX translate worker"
docker run -d \
  --name "$TRANSLATE_CONTAINER" \
  --network "$NETWORK" \
  -e "TRANSLATION_PROVIDER=mock" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$TRANSLATE_WORKER_IMAGE" \
  python /app/service/worker.py --consume --work-dir /tmp/file-translation/docx-translate >/dev/null

note "Starting DOCX replace worker"
docker run -d \
  --name "$DOCX_REPLACE_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$DOCX_REPLACE_WORKER_IMAGE" \
  python /app/service/worker.py --consume --work-dir /tmp/file-translation/docx-replace >/dev/null

note "Starting DOCX export worker"
docker run -d \
  --name "$DOCX_EXPORT_CONTAINER" \
  --network "$NETWORK" \
  -e "DOCX_EXPORT_PDF_MODE=placeholder" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$LIBREOFFICE_WORKER_IMAGE" \
  python /app/service/worker.py --consume --work-dir /tmp/file-translation/docx-export >/dev/null

note "Starting DOCX marker worker"
docker run -d \
  --name "$DOCX_MARKER_CONTAINER" \
  --network "$NETWORK" \
  -e "DOCX_MARKER_TOKEN=${DOCX_MARKER_TOKEN}" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$LIBREOFFICE_WORKER_IMAGE" \
  python /app/service/worker.py --consume-marker --work-dir /tmp/file-translation/docx-marker >/dev/null

note "Starting pdf2hwpx worker"
docker run -d \
  --name "$PDF2HWPX_CONTAINER" \
  --network "$NETWORK" \
  -e "MINIO_ENDPOINT=http://minio:9000" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  "$PDF2HWPX_WORKER_IMAGE" \
  python /app/service/worker.py --consume --work-dir /tmp/file-translation/pdf2hwpx >/dev/null

note "Starting email worker"
docker run -d \
  --name "$EMAIL_CONTAINER" \
  --network "$NETWORK" \
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

note "Waiting for DOCX route E2E completion and validating artifacts"
docker run --rm -i \
  --name "$VERIFY_DRIVER_CONTAINER" \
  --network "$NETWORK" \
  -e "JOB_SERVICE_URL=http://job-service:8080" \
  -e "MINIO_ENDPOINT=minio:9000" \
  -e "MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}" \
  -e "MINIO_SECRET_KEY=${MINIO_SECRET_KEY}" \
  -e "MINIO_BUCKET=${MINIO_BUCKET}" \
  -e "RABBITMQ_HOST=rabbitmq" \
  -e "RABBITMQ_USERNAME=${RABBITMQ_USERNAME}" \
  -e "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" \
  -e "DOCX_MARKER_TOKEN=${DOCX_MARKER_TOKEN}" \
  -v "$PWD/$OUT_DIR:/work/out" \
  "$EMAIL_WORKER_IMAGE" \
  python - <<'PY'
import io
import json
import os
import time
import zipfile
from pathlib import Path
from urllib import request
from xml.etree import ElementTree as ET

import pika
from minio import Minio

base_url = os.environ["JOB_SERVICE_URL"].rstrip("/")
setup = json.loads(Path("/work/out/e2e-setup.json").read_text(encoding="utf-8"))
job_id = setup["job_id"]
object_prefix = setup["object_prefix"]
bucket = os.environ["MINIO_BUCKET"]
marker_token = os.environ["DOCX_MARKER_TOKEN"]


def http_json(method: str, path: str) -> dict[str, object]:
    req = request.Request(f"{base_url}{path}", method=method)
    with request.urlopen(req, timeout=5) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise AssertionError("HTTP response must be a JSON object")
    return decoded


def wait_completed() -> dict[str, object]:
    last: dict[str, object] | None = None
    for _ in range(240):
        last = http_json("GET", f"/jobs/{job_id}")
        if last.get("status") == "failed":
            raise AssertionError(f"job failed: {last}")
        if last.get("status") == "completed" and last.get("current_stage") == "completed":
            return last
        time.sleep(1)
    raise AssertionError(f"job did not complete: {last}")


def get_object(key: str) -> bytes:
    response = client.get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def docx_texts(key: str) -> list[str]:
    data = get_object(key)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return [node.text or "" for node in root.findall(".//w:t", namespace)]


job = wait_completed()
client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False,
)
expected_keys = {
    "text_units": f"{object_prefix}/02_extract/text_units.json",
    "translated_units": f"{object_prefix}/03_translate/translated_units.json",
    "translated_docx": f"{object_prefix}/04_replace/translated.docx",
    "final_docx": f"{object_prefix}/05_export/final.docx",
    "final_pdf": f"{object_prefix}/05_export/final.pdf",
    "marker_docx": f"{object_prefix}/05_export/marker.docx",
    "final_hwpx": f"{object_prefix}/06_hwpx/final.hwpx",
    "email_report": f"{object_prefix}/reports/email_report.json",
}
artifacts = job.get("artifacts")
if not isinstance(artifacts, dict):
    raise AssertionError(f"job artifacts missing: {job}")
for name, key in expected_keys.items():
    if artifacts.get(name) != key:
        raise AssertionError(f"job artifact {name} expected {key}, got {artifacts.get(name)}")
    client.stat_object(bucket, key)

stages = job.get("stages")
if not isinstance(stages, dict):
    raise AssertionError(f"job stages missing: {job}")
for stage in [
    "docx_extract",
    "docx_translate",
    "docx_replace",
    "docx_export",
    "docx_marker",
    "pdf2hwpx",
    "email_send",
]:
    state = stages.get(stage)
    if not isinstance(state, dict) or state.get("status") != "completed":
        raise AssertionError(f"stage {stage} did not complete: {state}")

text_units = json.loads(get_object(expected_keys["text_units"]).decode("utf-8"))
translated_units = json.loads(get_object(expected_keys["translated_units"]).decode("utf-8"))
if text_units.get("input_type") != "docx" or len(text_units.get("units", [])) != 2:
    raise AssertionError(f"unexpected text_units payload: {text_units}")
if translated_units.get("provider") != "mock":
    raise AssertionError(f"unexpected translated_units provider: {translated_units}")
translated_values = [str(unit.get("translated", "")) for unit in translated_units.get("units", [])]
if "[ko] Hello world" not in translated_values or "[ko] Translate me" not in translated_values:
    raise AssertionError(f"translated units missing mock translations: {translated_values}")

translated_texts = docx_texts(expected_keys["translated_docx"])
if "[ko] Hello world" not in translated_texts or "[ko] Translate me" not in translated_texts:
    raise AssertionError(f"translated DOCX missing translated text: {translated_texts}")
final_docx_texts = docx_texts(expected_keys["final_docx"])
if final_docx_texts != translated_texts:
    raise AssertionError(f"final DOCX did not preserve translated text: {final_docx_texts}")
marker_texts = docx_texts(expected_keys["marker_docx"])
if not any(marker_token in text for text in marker_texts):
    raise AssertionError(f"marker DOCX did not contain marker token {marker_token!r}: {marker_texts}")
if not get_object(expected_keys["final_pdf"]).startswith(b"%PDF"):
    raise AssertionError("final_pdf artifact is not a PDF placeholder")

with zipfile.ZipFile(io.BytesIO(get_object(expected_keys["final_hwpx"]))) as archive:
    names = set(archive.namelist())
    if names != {"mimetype", "placeholder.json", "source/marker.docx"}:
        raise AssertionError(f"unexpected HWPX placeholder files: {names!r}")
    metadata = json.loads(archive.read("placeholder.json").decode("utf-8"))
    embedded_marker = archive.read("source/marker.docx")
if metadata.get("stage") != "pdf2hwpx" or metadata.get("placeholder") is not True:
    raise AssertionError(f"unexpected placeholder metadata: {metadata!r}")
if metadata.get("input_type") != "docx" or metadata.get("job_id") != job_id:
    raise AssertionError(f"unexpected placeholder route metadata: {metadata!r}")
with zipfile.ZipFile(io.BytesIO(embedded_marker)) as archive:
    root = ET.fromstring(archive.read("word/document.xml"))
namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
embedded_texts = [node.text or "" for node in root.findall(".//w:t", namespace)]
if embedded_texts != marker_texts:
    raise AssertionError(f"embedded marker DOCX mismatch: {embedded_texts} != {marker_texts}")

email_report = json.loads(get_object(expected_keys["email_report"]).decode("utf-8"))
if email_report.get("provider") != "mock" or email_report.get("status") != "sent":
    raise AssertionError(f"unexpected email report: {email_report}")
expected_attachments = [
    expected_keys["final_docx"],
    expected_keys["final_pdf"],
    expected_keys["final_hwpx"],
]
if email_report.get("attachments") != expected_attachments:
    raise AssertionError(f"unexpected email attachments: {email_report}")
if "token" in json.dumps(email_report).lower() or "password" in json.dumps(email_report).lower():
    raise AssertionError(f"email report contains secret-like field: {email_report}")

sendability = http_json("GET", f"/jobs/{job_id}/sendability")
if sendability.get("sendable") is not False:
    raise AssertionError(f"completed job should not be sendable: {sendability}")

credentials = pika.PlainCredentials(os.environ["RABBITMQ_USERNAME"], os.environ["RABBITMQ_PASSWORD"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()
stale: dict[str, list[dict[str, object]]] = {}
for queue in [
    "q.commands.docx_extract",
    "q.commands.docx_translate",
    "q.commands.docx_replace",
    "q.commands.docx_export",
    "q.commands.docx_marker",
    "q.commands.pdf2hwpx",
    "q.commands.email_send",
]:
    channel.queue_declare(queue=queue, durable=True)
    queue_stale: list[dict[str, object]] = []
    while True:
        method, _props, body = channel.basic_get(queue, auto_ack=True)
        if method is None:
            break
        decoded = json.loads(body.decode("utf-8"))
        if isinstance(decoded, dict):
            queue_stale.append(decoded)
    if queue_stale:
        stale[queue] = queue_stale
connection.close()
if stale:
    raise AssertionError(f"stale command queues were not empty: {stale}")

result = {
    **setup,
    "job": job,
    "expected_keys": expected_keys,
    "email_report": email_report,
    "sendability_after_completion": sendability,
}
Path("/work/out/e2e-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"job_id": job_id, "status": "completed", "email_report": expected_keys["email_report"]}, separators=(",", ":"), sort_keys=True))
PY

note "Checking PostgreSQL JSONB E2E state directly"
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

result = json.loads(Path("/work/out/e2e-result.json").read_text(encoding="utf-8"))
cancel = json.loads(Path("/work/out/cancel-result.json").read_text(encoding="utf-8"))
expected = result["expected_keys"]
job_id = result["job_id"]


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
        raise AssertionError(f"unexpected PostgreSQL JSONB payload: {payload!r}")
    return payload


payload = fetch(job_id)
if payload.get("status") != "completed" or payload.get("current_stage") != "completed":
    raise AssertionError(f"main DOCX E2E job did not complete in PostgreSQL: {payload}")
for stage in [
    "docx_extract",
    "docx_translate",
    "docx_replace",
    "docx_export",
    "docx_marker",
    "pdf2hwpx",
    "email_send",
]:
    state = payload.get("stages", {}).get(stage, {})
    if state.get("status") != "completed":
        raise AssertionError(f"PostgreSQL stage {stage} did not complete: {state}")
for name, key in expected.items():
    if payload.get("artifacts", {}).get(name) != key:
        raise AssertionError(f"PostgreSQL artifact {name} mismatch: {payload.get('artifacts')}")
for final_field, artifact_name in [
    ("final_docx_key", "final_docx"),
    ("final_pdf_key", "final_pdf"),
    ("final_hwpx_key", "final_hwpx"),
]:
    if payload.get(final_field) != expected[artifact_name]:
        raise AssertionError(f"PostgreSQL {final_field} mismatch: {payload.get(final_field)}")
if payload.get("translated_hwpx_key") is not None:
    raise AssertionError(f"DOCX route should not set translated_hwpx_key: {payload.get('translated_hwpx_key')}")

mid_cancel = fetch(cancel["mid_cancel_job_id"])
if mid_cancel.get("status") != "cancelled" or mid_cancel.get("current_stage") != "cancelled":
    raise AssertionError(f"mid-route cancellation did not persist as cancelled: {mid_cancel}")
email_cancel = fetch(cancel["email_cancel_job_id"])
if email_cancel.get("status") != "cancel_requested":
    raise AssertionError(f"email-stage cancellation did not persist cancel_requested: {email_cancel}")
print(json.dumps({"job_id": job_id, "postgres": "completed"}, separators=(",", ":"), sort_keys=True))
PY

push_uptime_kuma
pass "DOCX route E2E smoke completed"
