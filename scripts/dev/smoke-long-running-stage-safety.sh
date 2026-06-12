#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${LONG_RUNNING_SAFETY_SMOKE_PORT:-18082}"
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

log "Starting job-service long-running safety smoke server on ${BASE_URL}"
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

log "Exercising stage claim, lease, duplicate no-op, max-attempt, and email-send safety"
"$PYTHON_BIN" - "$BASE_URL" <<'PY'
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


def create_job(input_type: str, file_id: str) -> dict[str, object]:
    return request(
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


def claim(job_id: str, stage: str, command: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = {
        "command_id": command["command_id"],
        "attempt": command["attempt"],
        "worker_id": f"{stage}-worker:{stage}",
        "idempotency_key": command["idempotency_key"],
        "lease_seconds": command.get("lease_seconds", 300),
        "max_attempts": command.get("max_attempts", 3),
    }
    payload.update(overrides)
    return request("POST", f"/jobs/{job_id}/stages/{stage}/claim", payload)


pdf = create_job("pdf", "safetypdf")
pdf_job_id = str(pdf["job"]["job_id"])
pdf_command = dict(pdf["published_command"])

first_claim = claim(pdf_job_id, "pdf2docx", pdf_command)
if first_claim["claim_status"] != "CLAIMED" or first_claim["should_process"] is not True:
    raise SystemExit(f"expected first pdf2docx claim to process: {first_claim}")

duplicate_claim = claim(pdf_job_id, "pdf2docx", pdf_command)
if duplicate_claim["claim_status"] != "ALREADY_RUNNING" or duplicate_claim["should_process"] is not False:
    raise SystemExit(f"expected duplicate running no-op: {duplicate_claim}")

heartbeat = request(
    "POST",
    f"/jobs/{pdf_job_id}/stages/pdf2docx/heartbeat",
    {"claim_id": first_claim["claim_id"], "progress": 12},
)
if heartbeat["claim_status"] != "CLAIMED":
    raise SystemExit(f"heartbeat failed: {heartbeat}")

completed = request(
    "POST",
    "/events",
    {
        "event_type": "stage.completed",
        "job_id": pdf_job_id,
        "input_type": "pdf",
        "stage": "pdf2docx",
        "attempt": first_claim["attempt"],
        "claim_id": first_claim["claim_id"],
        "command_id": first_claim["command_id"],
        "outputs": {"converted_docx": "2026-01-21/12345678/safetypdf/01_pdf2docx/converted.docx"},
    },
)
if completed["published"] is not True or completed["published_command"]["stage"] != "docx_extract":
    raise SystemExit(f"expected docx_extract after first completion: {completed}")

duplicate_completed = request(
    "POST",
    "/events",
    {
        "event_type": "stage.completed",
        "job_id": pdf_job_id,
        "input_type": "pdf",
        "stage": "pdf2docx",
        "attempt": first_claim["attempt"],
        "claim_id": first_claim["claim_id"],
        "command_id": first_claim["command_id"],
    },
)
if duplicate_completed["published"] is not False:
    raise SystemExit(f"duplicate completed event published a command: {duplicate_completed}")

completed_stage_claim = claim(pdf_job_id, "pdf2docx", pdf_command)
if completed_stage_claim["claim_status"] != "ALREADY_COMPLETED":
    raise SystemExit(f"completed stage command should no-op: {completed_stage_claim}")

cancelled = create_job("hwpx", "safetycancel")
cancelled_job_id = str(cancelled["job"]["job_id"])
request("POST", f"/jobs/{cancelled_job_id}/cancel")
cancel_claim = claim(cancelled_job_id, "hwpx_extract", dict(cancelled["published_command"]))
if cancel_claim["claim_status"] != "JOB_CANCELLED" or cancel_claim["should_process"] is not False:
    raise SystemExit(f"cancelled job claim should not process: {cancel_claim}")

exhausted = create_job("pdf", "safetyexhausted")
exhausted_job_id = str(exhausted["job"]["job_id"])
exhausted_command = dict(exhausted["published_command"])
max_claim = claim(exhausted_job_id, "pdf2docx", exhausted_command, attempt=4, max_attempts=3)
if max_claim["claim_status"] != "MAX_ATTEMPTS_EXCEEDED":
    raise SystemExit(f"max attempts claim mismatch: {max_claim}")
if request("GET", f"/jobs/{exhausted_job_id}")["status"] != "failed":
    raise SystemExit("max attempts did not fail the job")

email = create_job("hwpx", "safetyemail")
email_job_id = str(email["job"]["job_id"])
for stage, outputs in [
    ("hwpx_extract", {"text_units": "2026-01-21/12345678/safetyemail/02_extract/text_units.json"}),
    ("hwpx_translate", {"translated_units": "2026-01-21/12345678/safetyemail/03_translate/translated_units.json"}),
    ("hwpx_replace", {"translated_hwpx": "2026-01-21/12345678/safetyemail/04_replace/translated.hwpx"}),
    (
        "hwpx_export",
        {
            "final_docx": "2026-01-21/12345678/safetyemail/05_export/final.docx",
            "final_pdf": "2026-01-21/12345678/safetyemail/05_export/final.pdf",
            "final_hwpx": "2026-01-21/12345678/safetyemail/06_hwpx/final.hwpx",
        },
    ),
]:
    response = request(
        "POST",
        "/events",
        {
            "event_type": "stage.completed",
            "job_id": email_job_id,
            "input_type": "hwpx",
            "stage": stage,
            "outputs": outputs,
        },
    )
email_command = dict(response["published_command"])
if email_command["stage"] != "email_send":
    raise SystemExit(f"expected email_send command: {response}")

email_claim = claim(email_job_id, "email_send", email_command)
if email_claim["claim_status"] != "CLAIMED":
    raise SystemExit(f"email claim failed: {email_claim}")
duplicate_email_claim = claim(email_job_id, "email_send", email_command)
if duplicate_email_claim["claim_status"] != "ALREADY_RUNNING" or duplicate_email_claim["should_process"] is not False:
    raise SystemExit(f"duplicate email command should no-op before send: {duplicate_email_claim}")

request(
    "POST",
    "/events",
    {
        "event_type": "stage.completed",
        "job_id": email_job_id,
        "input_type": "hwpx",
        "stage": "email_send",
        "attempt": email_claim["attempt"],
        "claim_id": email_claim["claim_id"],
        "command_id": email_claim["command_id"],
        "outputs": {"email_report": "2026-01-21/12345678/safetyemail/reports/email_report.json"},
    },
)
post_send_claim = claim(email_job_id, "email_send", email_command)
if post_send_claim["claim_status"] != "ALREADY_COMPLETED" or post_send_claim["should_process"] is not False:
    raise SystemExit(f"completed email command should no-op: {post_send_claim}")

print(
    json.dumps(
        {
            "pdf_job_id": pdf_job_id,
            "duplicate_claim": duplicate_claim["claim_status"],
            "duplicate_completed_published": duplicate_completed["published"],
            "cancel_claim": cancel_claim["claim_status"],
            "max_attempts": max_claim["claim_status"],
            "email_duplicate": duplicate_email_claim["claim_status"],
            "email_completed_duplicate": post_send_claim["claim_status"],
        },
        sort_keys=True,
    )
)
PY

pass "long-running stage safety smoke completed"
