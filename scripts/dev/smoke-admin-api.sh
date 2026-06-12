#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${ADMIN_API_SMOKE_PORT:-18081}"
BASE_URL="http://127.0.0.1:${PORT}"

log() {
  printf '[INFO] %s\n' "$*"
}

pass() {
  printf '[PASS] %s\n' "$*"
}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"

log "Starting job-service API smoke server on ${BASE_URL}"
"$PYTHON_BIN" services/job-service/app.py --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!

log "Waiting for job-service readiness"
"$PYTHON_BIN" - "$BASE_URL" <<'PY'
from __future__ import annotations

import json
import sys
import time
from urllib.request import urlopen

base_url = sys.argv[1]
deadline = time.time() + 20
while time.time() < deadline:
    try:
        with urlopen(f"{base_url}/readyz", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "ok":
            raise SystemExit(0)
    except Exception:
        time.sleep(0.5)
raise SystemExit("job-service did not become ready")
PY

log "Exercising public/admin job-service APIs"
"$PYTHON_BIN" - "$BASE_URL" <<'PY'
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError
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


def create_job(input_type: str, file_id: str) -> str:
    payload = request(
        "POST",
        "/jobs",
        {
            "user_id": "12345678",
            "input_type": input_type,
            "source_lang": "en",
            "target_lang": "ko",
            "original_filename": f"{file_id}.{input_type}",
            "file_id": file_id,
            "input_object_key": f"2026-01-21/12345678/{file_id}/input/original.{input_type}",
        },
    )
    return str(payload["job"]["job_id"])


completed_job_id = create_job("docx", "adminapidocx")
for stage, outputs in [
    ("docx_extract", {"text_units": "2026-01-21/12345678/adminapidocx/02_extract/text_units.json"}),
    ("docx_translate", {"translated_units": "2026-01-21/12345678/adminapidocx/03_translate/translated_units.json"}),
    ("docx_replace", {"translated_docx": "2026-01-21/12345678/adminapidocx/04_replace/translated.docx"}),
    (
        "docx_export",
        {
            "final_docx": "2026-01-21/12345678/adminapidocx/05_export/final.docx",
            "final_pdf": "2026-01-21/12345678/adminapidocx/05_export/final.pdf",
        },
    ),
    ("docx_marker", {"marker_docx": "2026-01-21/12345678/adminapidocx/05_export/marker.docx"}),
    ("pdf2hwpx", {"final_hwpx": "2026-01-21/12345678/adminapidocx/06_hwpx/final.hwpx"}),
    ("email_send", {"email_report": "2026-01-21/12345678/adminapidocx/reports/email_report.json"}),
]:
    request(
        "POST",
        "/events",
        {
            "event_type": "stage.completed",
            "job_id": completed_job_id,
            "input_type": "docx",
            "stage": stage,
            "outputs": outputs,
        },
    )

cancel_job_id = create_job("hwpx", "adminapicancel")
cancelled = request("POST", f"/jobs/{cancel_job_id}/cancel")
if cancelled["status"] != "cancel_requested":
    raise SystemExit(f"cancel status mismatch: {cancelled}")

failed_job_id = create_job("pdf", "adminapifailed")
request(
    "POST",
    "/events",
    {
        "event_type": "stage.failed",
        "job_id": failed_job_id,
        "input_type": "pdf",
        "stage": "pdf2docx",
        "error_message": "converter failed",
    },
)

detail = request("GET", f"/jobs/{completed_job_id}")
stages = request("GET", f"/jobs/{completed_job_id}/stages")
artifacts = request("GET", f"/jobs/{completed_job_id}/artifacts")
admin_jobs = request("GET", "/admin/jobs")
admin_completed = request("GET", "/admin/jobs?status=completed")
admin_cancelled = request("GET", "/admin/jobs?status=cancel_requested")
admin_failed = request("GET", "/admin/jobs?status=failed")
admin_detail = request("GET", f"/admin/jobs/{completed_job_id}")

if detail["status"] != "completed" or detail["current_stage"] != "completed":
    raise SystemExit(f"completed job state mismatch: {detail}")
if not any(stage["stage"] == "email_send" and stage["status"] == "completed" for stage in stages["stages"]):
    raise SystemExit("email_send completed stage missing")
if not any(item["artifact_type"] == "email_report" for item in artifacts["artifacts"]):
    raise SystemExit("email_report artifact missing")
if admin_jobs["count"] != 3:
    raise SystemExit(f"expected 3 admin jobs, got {admin_jobs['count']}")
if admin_completed["count"] != 1 or admin_cancelled["count"] != 1 or admin_failed["count"] != 1:
    raise SystemExit("admin status filters did not find completed/cancel_requested/failed jobs")
if admin_detail["summary"]["job_id"] != completed_job_id:
    raise SystemExit("admin detail summary mismatch")
if not any(item["artifact_type"] == "final_hwpx" for item in admin_detail["artifacts"]):
    raise SystemExit("admin detail final_hwpx artifact missing")

retried = request("POST", f"/jobs/{failed_job_id}/retry")
if retried["queue"] != "q.commands.pdf2docx" or retried["published_command"]["attempt"] != 2:
    raise SystemExit(f"retry payload mismatch: {retried}")

try:
    request("POST", f"/jobs/{completed_job_id}/retry")
except HTTPError as exc:
    if exc.code != 409:
        raise
else:
    raise SystemExit("retry on completed job unexpectedly succeeded")

with urlopen(f"{base_url}/admin", timeout=10) as response:
    html = response.read().decode("utf-8")
if "File Translation Admin" not in html or "/admin/jobs" not in html or "RabbitMQ" in html:
    raise SystemExit("admin HTML boundary check failed")

print(
    json.dumps(
        {
            "completed_job_id": completed_job_id,
            "cancel_job_id": cancel_job_id,
            "failed_job_id": failed_job_id,
            "admin_job_count": admin_jobs["count"],
            "retry_queue": retried["queue"],
        },
        sort_keys=True,
    )
)
PY

pass "job-service admin API smoke completed"
