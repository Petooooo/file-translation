#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${RETRY_BACKOFF_DLQ_SMOKE_PORT:-18085}"
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

log "Starting job-service retry/backoff/DLQ smoke server on ${BASE_URL}"
STAGE_RETRY_BACKOFF_SECONDS="${STAGE_RETRY_BACKOFF_SECONDS:-1,1,1}" \
STALE_LEASE_RECONCILE_INTERVAL_SECONDS="${STALE_LEASE_RECONCILE_INTERVAL_SECONDS:-300}" \
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

log "Exercising delayed retry, backoff, logical DLQ, and email no-auto-retry behavior"
"$PYTHON_BIN" - "$BASE_URL" <<'PY'
from __future__ import annotations

import json
import sys
import time
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


stale = create_job("pdf", "retrybackoffstale")
stale_job_id = str(stale["job"]["job_id"])
stale_command = dict(stale["published_command"])
stale_claim = claim(stale_job_id, "pdf2docx", stale_command, lease_seconds=-1)
if stale_claim["claim_status"] != "CLAIMED":
    raise SystemExit(f"stale claim failed: {stale_claim}")

scheduled = request("POST", "/internal/reconcile/stale-leases", {"retry_backoff_seconds": 2})
if scheduled["retry_pending"] != 1 or scheduled["retried"] != 0 or scheduled["published_commands"]:
    raise SystemExit(f"retry should be pending before backoff elapses: {scheduled}")
pending_job = request("GET", f"/jobs/{stale_job_id}")
pending_stage = pending_job["stages"]["pdf2docx"]
if pending_stage["status"] != "retry_pending" or pending_stage["retry_backoff_seconds"] != 2:
    raise SystemExit(f"retry pending metadata mismatch: {pending_stage}")
if not pending_stage["failed_attempts"] or pending_stage["last_failed_command"]["command_id"] != stale_claim["command_id"]:
    raise SystemExit(f"failed attempt metadata missing: {pending_stage}")

too_early = request("POST", "/internal/reconcile/stale-leases")
if too_early["retried"] != 0:
    raise SystemExit(f"retry command was published before next_retry_at: {too_early}")
time.sleep(2.2)
due = request("POST", "/internal/reconcile/stale-leases")
if due["retried"] != 1:
    raise SystemExit(f"retry command was not published after backoff: {due}")
retry_command = due["published_commands"][0]["message"]
if retry_command["stage"] != "pdf2docx" or retry_command["attempt"] != 2:
    raise SystemExit(f"unexpected due retry command: {retry_command}")

late_event = request(
    "POST",
    "/events",
    {
        "event_type": "stage.completed",
        "job_id": stale_job_id,
        "input_type": "pdf",
        "stage": "pdf2docx",
        "attempt": 1,
        "claim_id": stale_claim["claim_id"],
        "command_id": stale_claim["command_id"],
    },
)
if late_event["published"] is not False:
    raise SystemExit(f"late previous-attempt event should no-op: {late_event}")

failed = create_job("docx", "retrybackofffailed")
failed_job_id = str(failed["job"]["job_id"])
failed_command = dict(failed["published_command"])
failed_claim = claim(failed_job_id, "docx_extract", failed_command)
failure_event = request(
    "POST",
    "/events",
    {
        "event_type": "stage.failed",
        "job_id": failed_job_id,
        "input_type": "docx",
        "stage": "docx_extract",
        "attempt": failed_claim["attempt"],
        "claim_id": failed_claim["claim_id"],
        "command_id": failed_claim["command_id"],
        "error_message": "extract failed transiently",
    },
)
if failure_event["published"] is not False:
    raise SystemExit(f"failed event should schedule retry without immediate publish: {failure_event}")
failed_job = request("GET", f"/jobs/{failed_job_id}")
failed_stage = failed_job["stages"]["docx_extract"]
if failed_stage["status"] != "retry_pending" or failed_stage["retry_backoff_seconds"] != 1:
    raise SystemExit(f"stage.failed did not schedule delayed retry: {failed_stage}")
time.sleep(1.2)
failed_due = request("POST", "/internal/reconcile/stale-leases")
if failed_due["retried"] != 1 or failed_due["published_commands"][0]["message"]["stage"] != "docx_extract":
    raise SystemExit(f"failed-stage retry did not publish when due: {failed_due}")

exhausted = create_job("pdf", "retrybackoffdlq")
exhausted_job_id = str(exhausted["job"]["job_id"])
exhausted_command = dict(exhausted["published_command"])
claim(
    exhausted_job_id,
    "pdf2docx",
    exhausted_command,
    command_id=f"{exhausted_job_id}:pdf2docx:3",
    attempt=3,
    idempotency_key=f"{exhausted_job_id}:pdf2docx:3",
    lease_seconds=-1,
    max_attempts=3,
)
terminal = request("POST", "/internal/reconcile/stale-leases")
terminal_job = request("GET", f"/jobs/{exhausted_job_id}")
terminal_stage = terminal_job["stages"]["pdf2docx"]
if terminal["failed"] != 1 or terminal["dlq"] != 1 or terminal_job["status"] != "failed":
    raise SystemExit(f"max-attempt stale lease should become logical DLQ: result={terminal} job={terminal_job}")
for key in ("failed_attempts", "last_failed_command", "terminal_failure_reason", "dlq_reason", "failed_record"):
    if not terminal_stage.get(key):
        raise SystemExit(f"terminal failed stage missing {key}: {terminal_stage}")

email = create_job("hwpx", "retrybackoffemail")
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
claim(email_job_id, "email_send", email_command, lease_seconds=-1)
email_result = request("POST", "/internal/reconcile/stale-leases")
email_job = request("GET", f"/jobs/{email_job_id}")
email_stage = email_job["stages"]["email_send"]
if email_result["failed"] != 1 or email_result["retried"] != 0 or email_job["error_stage"] != "email_send":
    raise SystemExit(f"stale email_send should fail without retry: result={email_result} job={email_job}")
if email_stage["dlq_reason"] != "email_send_stale_no_auto_retry":
    raise SystemExit(f"email stale logical DLQ reason mismatch: {email_stage}")

health = request("GET", "/admin/health")
if health["failed_job_count"] < 2:
    raise SystemExit(f"admin health did not expose logical DLQ failures: {health}")

print(
    json.dumps(
        {
            "stale_retry_attempt": retry_command["attempt"],
            "stage_failed_retry_attempt": failed_due["published_commands"][0]["message"]["attempt"],
            "terminal_dlq_reason": terminal_stage["dlq_reason"],
            "email_dlq_reason": email_stage["dlq_reason"],
            "failed_job_count": health["failed_job_count"],
        },
        sort_keys=True,
    )
)
PY

pass "retry/backoff/DLQ smoke completed"
