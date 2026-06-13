#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${STALE_LEASE_RECONCILER_SMOKE_PORT:-18083}"
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

log "Starting job-service stale lease reconciler smoke server on ${BASE_URL}"
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

log "Exercising stale lease retry, stale event no-op, failed terminal, cancel, and email no-send safety"
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
        "lease_seconds": -1,
        "max_attempts": command.get("max_attempts", 3),
    }
    payload.update(overrides)
    return request("POST", f"/jobs/{job_id}/stages/{stage}/claim", payload)


stale = create_job("pdf", "staleleasepdf")
stale_job_id = str(stale["job"]["job_id"])
stale_command = dict(stale["published_command"])
first_claim = claim(stale_job_id, "pdf2docx", stale_command)
if first_claim["claim_status"] != "CLAIMED":
    raise SystemExit(f"stale pdf2docx claim failed: {first_claim}")

retry_result = request("POST", "/internal/reconcile/stale-leases", {"retry_backoff_seconds": 0})
if retry_result["retry_pending"] != 1 or retry_result["retried"] != 0 or retry_result["failed"] != 0:
    raise SystemExit(f"expected one stale retry to be scheduled: {retry_result}")
if retry_result["published_commands"]:
    raise SystemExit(f"retry command was published before next_retry_at: {retry_result}")

late_event = request(
    "POST",
    "/events",
    {
        "event_type": "stage.completed",
        "job_id": stale_job_id,
        "input_type": "pdf",
        "stage": "pdf2docx",
        "attempt": 1,
        "claim_id": first_claim["claim_id"],
        "command_id": first_claim["command_id"],
        "outputs": {"converted_docx": "should/not/be/applied.docx"},
    },
)
if late_event["published"] is not False:
    raise SystemExit(f"late previous-attempt event published a command: {late_event}")
stale_job = request("GET", f"/jobs/{stale_job_id}")
stale_stage = stale_job["stages"]["pdf2docx"]
if stale_job["current_stage"] != "pdf2docx" or stale_stage["attempts"] != 2:
    raise SystemExit(f"late event changed current attempt state: {stale_job}")
if stale_stage["status"] != "retry_pending":
    raise SystemExit(f"expected retry pending after first reconcile: {stale_stage}")
if stale_stage["last_reconcile_reason"] != "stale_lease_expired":
    raise SystemExit(f"missing retry reconcile reason: {stale_stage}")

due_result = request("POST", "/internal/reconcile/stale-leases")
if due_result["retried"] != 1:
    raise SystemExit(f"expected retry command after next_retry_at: {due_result}")
retry_command = due_result["published_commands"][0]["message"]
if retry_command["stage"] != "pdf2docx" or retry_command["attempt"] != 2:
    raise SystemExit(f"unexpected retry command: {retry_command}")
stale_job = request("GET", f"/jobs/{stale_job_id}")
stale_stage = stale_job["stages"]["pdf2docx"]
if stale_stage["status"] != "running" or stale_stage["next_retry_at"] is not None:
    raise SystemExit(f"retry pending did not release to running command state: {stale_stage}")

exhausted = create_job("pdf", "staleexhausted")
exhausted_job_id = str(exhausted["job"]["job_id"])
exhausted_command = dict(exhausted["published_command"])
claim(
    exhausted_job_id,
    "pdf2docx",
    exhausted_command,
    command_id=f"{exhausted_job_id}:pdf2docx:3",
    attempt=3,
    idempotency_key=f"{exhausted_job_id}:pdf2docx:3",
    max_attempts=3,
)
failed_result = request("POST", "/internal/reconcile/stale-leases")
failed_job = request("GET", f"/jobs/{exhausted_job_id}")
if failed_result["failed"] != 1 or failed_job["status"] != "failed":
    raise SystemExit(f"expected exhausted stale lease to fail: result={failed_result} job={failed_job}")
if failed_job["stages"]["pdf2docx"]["last_reconcile_reason"] != "max_attempts_exceeded":
    raise SystemExit(f"unexpected exhausted reason: {failed_job['stages']['pdf2docx']}")

cancelled = create_job("hwpx", "stalecancel")
cancelled_job_id = str(cancelled["job"]["job_id"])
claim(cancelled_job_id, "hwpx_extract", dict(cancelled["published_command"]))
request("POST", f"/jobs/{cancelled_job_id}/cancel")
cancel_result = request("POST", "/internal/reconcile/stale-leases")
cancel_job = request("GET", f"/jobs/{cancelled_job_id}")
if cancel_result["cancelled"] != 1 or cancel_job["status"] != "cancelled":
    raise SystemExit(f"cancelled stale lease retried or remained open: result={cancel_result} job={cancel_job}")

email = create_job("hwpx", "staleemail")
email_job_id = str(email["job"]["job_id"])
event_response: dict[str, object] | None = None
for stage in ["hwpx_extract", "hwpx_translate", "hwpx_replace", "hwpx_export"]:
    event_response = request(
        "POST",
        "/events",
        {
            "event_type": "stage.completed",
            "job_id": email_job_id,
            "input_type": "hwpx",
            "stage": stage,
        },
    )
if event_response is None or event_response["published_command"]["stage"] != "email_send":
    raise SystemExit(f"job did not reach email_send: {event_response}")
email_command = dict(event_response["published_command"])
email_claim = claim(email_job_id, "email_send", email_command)
if email_claim["claim_status"] != "CLAIMED":
    raise SystemExit(f"email claim failed: {email_claim}")

email_result = request("POST", "/internal/reconcile/stale-leases")
email_job = request("GET", f"/jobs/{email_job_id}")
if email_result["failed"] != 1 or email_result["retried"] != 0:
    raise SystemExit(f"stale email_send should fail without auto retry: {email_result}")
if email_job["error_stage"] != "email_send":
    raise SystemExit(f"email stale failure did not mark error_stage: {email_job}")
if email_job["stages"]["email_send"]["last_reconcile_reason"] != "email_send_stale_no_auto_retry":
    raise SystemExit(f"unexpected email reconcile reason: {email_job['stages']['email_send']}")

print(
    json.dumps(
        {
            "retry_job_id": stale_job_id,
            "retry_attempt": stale_stage["attempts"],
            "retry_command_attempt": retry_command["attempt"],
            "late_event_published": late_event["published"],
            "exhausted_job_status": failed_job["status"],
            "cancelled_job_status": cancel_job["status"],
            "email_job_status": email_job["status"],
        },
        sort_keys=True,
    )
)
PY

pass "stale lease reconciler smoke completed"
