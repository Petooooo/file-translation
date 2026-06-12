#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HEALTHY_PORT="${MONITORING_SMOKE_PORT:-18082}"
UNHEALTHY_PORT="${MONITORING_SMOKE_UNHEALTHY_PORT:-18083}"
HEALTHY_URL="http://127.0.0.1:${HEALTHY_PORT}"
UNHEALTHY_URL="http://127.0.0.1:${UNHEALTHY_PORT}"

HEALTHY_PID=""
UNHEALTHY_PID=""

log() {
  printf '[INFO] %s\n' "$*"
}

pass() {
  printf '[PASS] %s\n' "$*"
}

cleanup() {
  if [[ -n "$HEALTHY_PID" ]]; then
    kill "$HEALTHY_PID" >/dev/null 2>&1 || true
    wait "$HEALTHY_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$UNHEALTHY_PID" ]]; then
    kill "$UNHEALTHY_PID" >/dev/null 2>&1 || true
    wait "$UNHEALTHY_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"

wait_for_healthz() {
  local base_url="$1"
  "$PYTHON_BIN" - "$base_url" <<'PY'
from __future__ import annotations

import json
import sys
import time
from urllib.request import urlopen

base_url = sys.argv[1]
deadline = time.time() + 20
while time.time() < deadline:
    try:
        with urlopen(f"{base_url}/healthz", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "ok":
            raise SystemExit(0)
    except Exception:
        time.sleep(0.5)
raise SystemExit(f"{base_url} did not become healthy")
PY
}

log "Starting healthy job-service monitoring smoke server on ${HEALTHY_URL}"
"$PYTHON_BIN" services/job-service/app.py --host 127.0.0.1 --port "$HEALTHY_PORT" &
HEALTHY_PID=$!
wait_for_healthz "$HEALTHY_URL"

log "Validating healthy monitoring endpoints"
"$PYTHON_BIN" - "$HEALTHY_URL" <<'PY'
from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

base_url = sys.argv[1]


def request(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


healthz = request("GET", "/healthz")
readyz = request("GET", "/readyz")
admin_health = request("GET", "/admin/health")
queues = request("GET", "/admin/queues")
workers = request("GET", "/admin/workers")

if healthz["status"] != "ok":
    raise SystemExit(f"healthz mismatch: {healthz}")
if readyz["status"] != "ok" or readyz["overall_status"] != "healthy":
    raise SystemExit(f"readyz mismatch: {readyz}")
if admin_health["overall_status"] != "healthy":
    raise SystemExit(f"admin health mismatch: {admin_health}")
for dependency in ("postgresql", "rabbitmq", "minio"):
    if admin_health["dependencies"][dependency]["status"] != "skipped":
        raise SystemExit(f"expected skipped dependency {dependency}: {admin_health}")
if queues["status"] != "skipped":
    raise SystemExit(f"queue summary mismatch: {queues}")
if not any(queue["name"] == "q.commands.pdf2docx" for queue in queues["queues"]):
    raise SystemExit("configured pdf2docx command queue missing from queue summary")
if workers["heartbeat_available"] is not False or workers["source"] != "job_stage_events":
    raise SystemExit(f"worker summary mismatch: {workers}")

created = request(
    "POST",
    "/jobs",
    {
        "user_id": "12345678",
        "input_type": "docx",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "monitoring.docx",
        "file_id": "monitoringdocx",
        "input_object_key": "2026-01-21/12345678/monitoringdocx/input/original.docx",
    },
)
job_id = created["job"]["job_id"]
request(
    "POST",
    "/events",
    {
        "event_type": "stage.completed",
        "job_id": job_id,
        "input_type": "docx",
        "stage": "docx_extract",
        "outputs": {"text_units": "2026-01-21/12345678/monitoringdocx/02_extract/text_units.json"},
    },
)
workers = request("GET", "/admin/workers")
docx_extract = next(item for item in workers["workers"] if item["handled_stage"] == "docx_extract")
if docx_extract["counts"]["completed"] != 1 or docx_extract["status"] not in {"observed", "running"}:
    raise SystemExit(f"event-derived worker summary mismatch: {docx_extract}")

stale = request(
    "POST",
    "/jobs",
    {
        "user_id": "12345678",
        "input_type": "pdf",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "monitoring-stale.pdf",
        "file_id": "monitoringstale",
        "input_object_key": "2026-01-21/12345678/monitoringstale/input/original.pdf",
    },
)
stale_job_id = stale["job"]["job_id"]
stale_command = stale["published_command"]
request(
    "POST",
    f"/jobs/{stale_job_id}/stages/pdf2docx/claim",
    {
        "command_id": stale_command["command_id"],
        "attempt": stale_command["attempt"],
        "worker_id": "pdf2docx-worker:pdf2docx",
        "idempotency_key": stale_command["idempotency_key"],
        "lease_seconds": -1,
        "max_attempts": 3,
    },
)
stale_health = request("GET", "/admin/health")
if stale_health["overall_status"] != "degraded" or stale_health["stale_running_count"] != 1:
    raise SystemExit(f"stale running count missing from admin health: {stale_health}")
if stale_health["job_summary"]["stale_running_stages"][0]["job_id"] != stale_job_id:
    raise SystemExit(f"stale running stage details missing: {stale_health}")

reconciled = request("POST", "/internal/reconcile/stale-leases")
if reconciled["retried"] != 1:
    raise SystemExit(f"expected stale retry during monitoring smoke: {reconciled}")
recovered_health = request("GET", "/admin/health")
if recovered_health["stale_running_count"] != 0:
    raise SystemExit(f"stale running count did not clear after reconcile: {recovered_health}")

failed = request(
    "POST",
    "/jobs",
    {
        "user_id": "12345678",
        "input_type": "pdf",
        "source_lang": "en",
        "target_lang": "ko",
        "original_filename": "monitoring-failed.pdf",
        "file_id": "monitoringfailed",
        "input_object_key": "2026-01-21/12345678/monitoringfailed/input/original.pdf",
    },
)
failed_job_id = failed["job"]["job_id"]
failed_command = failed["published_command"]
request(
    "POST",
    f"/jobs/{failed_job_id}/stages/pdf2docx/claim",
    {
        "command_id": f"{failed_job_id}:pdf2docx:3",
        "attempt": 3,
        "worker_id": "pdf2docx-worker:pdf2docx",
        "idempotency_key": f"{failed_job_id}:pdf2docx:3",
        "lease_seconds": -1,
        "max_attempts": failed_command.get("max_attempts", 3),
    },
)
failed_reconcile = request("POST", "/internal/reconcile/stale-leases")
failed_health = request("GET", "/admin/health")
if failed_reconcile["failed"] != 1:
    raise SystemExit(f"expected max-attempt stale failure: {failed_reconcile}")
if failed_health["failed_job_count"] < 1 or not failed_health["recent_failed_jobs"]:
    raise SystemExit(f"failed job summary missing from admin health: {failed_health}")

with urlopen(f"{base_url}/admin", timeout=10) as response:
    html = response.read().decode("utf-8")
if "File Translation Admin" not in html or "/admin/health" not in html or "/admin/queues" not in html:
    raise SystemExit("admin HTML monitoring links missing")
if "q.commands" in html or "RABBITMQ_PASSWORD" in html:
    raise SystemExit("admin HTML exposed internal queue names or credentials")

print(json.dumps({"healthy_overall": admin_health["overall_status"], "job_id": job_id}, sort_keys=True))
PY

log "Starting intentionally unhealthy dependency monitoring server on ${UNHEALTHY_URL}"
JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq \
RABBITMQ_HOST=127.0.0.1 \
RABBITMQ_PORT=9 \
MINIO_ENDPOINT=http://127.0.0.1:9 \
MINIO_ACCESS_KEY=minioadmin \
MINIO_SECRET_KEY=minioadmin \
  "$PYTHON_BIN" services/job-service/app.py --host 127.0.0.1 --port "$UNHEALTHY_PORT" &
UNHEALTHY_PID=$!
wait_for_healthz "$UNHEALTHY_URL"

log "Validating degraded/unhealthy monitoring responses"
"$PYTHON_BIN" - "$UNHEALTHY_URL" <<'PY'
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

base_url = sys.argv[1]


def get_json_allow_error(path: str) -> tuple[int, dict[str, object]]:
    try:
        with urlopen(f"{base_url}{path}", timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


ready_code, readyz = get_json_allow_error("/readyz")
health_code, admin_health = get_json_allow_error("/admin/health")
queue_code, queues = get_json_allow_error("/admin/queues")
healthz_code, healthz = get_json_allow_error("/healthz")

if healthz_code != 200 or healthz["status"] != "ok":
    raise SystemExit(f"healthz should stay process-alive ok: {healthz_code} {healthz}")
if ready_code != 503 or readyz["overall_status"] != "unhealthy":
    raise SystemExit(f"readyz unhealthy mismatch: {ready_code} {readyz}")
if health_code != 503 or admin_health["dependencies"]["rabbitmq"]["status"] != "unhealthy":
    raise SystemExit(f"admin health unhealthy mismatch: {health_code} {admin_health}")
if admin_health["dependencies"]["minio"]["status"] != "unhealthy":
    raise SystemExit(f"minio unhealthy dependency missing: {admin_health}")
if queue_code != 503 or queues["status"] != "unhealthy":
    raise SystemExit(f"queue unhealthy mismatch: {queue_code} {queues}")

print(
    json.dumps(
        {
            "readyz": readyz["overall_status"],
            "rabbitmq": admin_health["dependencies"]["rabbitmq"]["status"],
            "minio": admin_health["dependencies"]["minio"]["status"],
            "queues": queues["status"],
        },
        sort_keys=True,
    )
)
PY

pass "monitoring readiness smoke completed"
