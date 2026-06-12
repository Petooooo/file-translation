"""Tiny stdlib HTTP API for job-service routing skeleton."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

from ft_common.config import AppConfig
from ft_common.health import health_payload
from job_service.monitoring import (
    admin_health_payload,
    queue_summary_payload,
    readiness_payload,
    worker_summary_payload,
)
from job_service.orchestrator import JobRetryNotAllowedError, JobService
from job_service.repository import JobNotFoundError


def make_handler(config: AppConfig, service: JobService) -> type[BaseHTTPRequestHandler]:
    class JobServiceHandler(BaseHTTPRequestHandler):
        server_version = "file-translation-job-service/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            static_routes: dict[str, Callable[[], tuple[int, dict[str, object]]]] = {
                "/healthz": lambda: (200, health_payload(config)),
                "/readyz": self._readyz,
                "/config": lambda: (200, config.safe_dict()),
            }
            if path == "/admin":
                self._write_html(200, ADMIN_HTML)
                return
            if path in static_routes:
                code, payload = static_routes[path]()
                self._write_json(code, payload)
                return

            parts = _parts(path)
            if parts == ["admin", "jobs"]:
                self._write_admin_jobs(_filters(parsed.query))
                return
            if parts == ["admin", "health"]:
                self._write_admin_health()
                return
            if parts == ["admin", "workers"]:
                self._write_json(200, worker_summary_payload(service))
                return
            if parts == ["admin", "queues"]:
                payload = queue_summary_payload(config)
                code = 503 if payload["status"] == "unhealthy" else 200
                self._write_json(code, payload)
                return
            if len(parts) == 3 and parts[0] == "admin" and parts[1] == "jobs":
                self._write_admin_job(parts[2])
                return
            if len(parts) == 2 and parts[0] == "jobs":
                self._write_job(parts[1])
                return
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "stages":
                self._write_job_stages(parts[1])
                return
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "artifacts":
                self._write_job_artifacts(parts[1])
                return
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "sendability":
                self._write_sendability(parts[1])
                return

            self._write_json(404, {"status": "not_found", "path": path})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            parts = _parts(path)
            if parts == ["jobs"]:
                self._create_job()
                return
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "cancel":
                self._cancel_job(parts[1])
                return
            if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "retry":
                self._retry_job(parts[1])
                return
            if len(parts) == 5 and parts[0] == "jobs" and parts[2] == "stages" and parts[4] == "claim":
                self._claim_stage(parts[1], parts[3])
                return
            if len(parts) == 5 and parts[0] == "jobs" and parts[2] == "stages" and parts[4] == "heartbeat":
                self._heartbeat_stage(parts[1], parts[3])
                return
            if parts == ["internal", "reconcile", "stale-leases"]:
                self._reconcile_stale_leases()
                return
            if parts == ["events"]:
                self._handle_event()
                return

            self._write_json(404, {"status": "not_found", "path": path})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _readyz(self) -> tuple[int, dict[str, object]]:
            payload = readiness_payload(config, service)
            code = 503 if payload["overall_status"] == "unhealthy" else 200
            return code, payload

        def _write_admin_health(self) -> None:
            payload = admin_health_payload(config, service)
            code = 503 if payload["overall_status"] == "unhealthy" else 200
            self._write_json(code, payload)

        def _create_job(self) -> None:
            try:
                payload = self._read_json()
                job, command = service.create_job(
                    user_id=str(payload["user_id"]),
                    input_type=str(payload["input_type"]),
                    source_lang=str(payload.get("source_lang", "auto")),
                    target_lang=str(payload["target_lang"]),
                    original_filename=str(payload["original_filename"]),
                    file_id=_optional_str(payload.get("file_id")),
                    input_object_key=_optional_str(payload.get("input_object_key")),
                )
            except (KeyError, ValueError) as exc:
                self._write_json(400, {"status": "bad_request", "error": str(exc)})
                return

            self._write_json(201, {"job": job.to_dict(), "published_command": command.message, "queue": command.queue})

        def _write_job(self, job_id: str) -> None:
            try:
                self._write_json(200, service.get_job(job_id).to_dict())
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _write_job_stages(self, job_id: str) -> None:
            try:
                self._write_json(200, service.stages_payload(job_id))
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _write_job_artifacts(self, job_id: str) -> None:
            try:
                self._write_json(200, service.artifacts_payload(job_id))
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _write_admin_jobs(self, filters: dict[str, str]) -> None:
            jobs = service.list_jobs(filters)
            self._write_json(
                200,
                {
                    "jobs": [service.job_summary(job) for job in jobs],
                    "count": len(jobs),
                    "filters": filters,
                },
            )

        def _write_admin_job(self, job_id: str) -> None:
            try:
                job = service.get_job(job_id)
                self._write_json(
                    200,
                    {
                        "job": job.to_dict(),
                        "summary": service.job_summary(job),
                        "stages": service.stages_payload(job_id)["stages"],
                        "artifacts": service.artifacts_payload(job_id)["artifacts"],
                    },
                )
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _cancel_job(self, job_id: str) -> None:
            try:
                self._write_json(200, service.cancel_job(job_id).to_dict())
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _retry_job(self, job_id: str) -> None:
            try:
                payload = self._read_json()
                job, command = service.retry_job(job_id, stage=_optional_str(payload.get("stage")))
                self._write_json(202, {"job": job.to_dict(), "published_command": command.message, "queue": command.queue})
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})
            except (JobRetryNotAllowedError, ValueError) as exc:
                self._write_json(409, {"status": "retry_not_allowed", "job_id": job_id, "error": str(exc)})

        def _write_sendability(self, job_id: str) -> None:
            try:
                self._write_json(200, service.sendability(job_id))
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _claim_stage(self, job_id: str, stage: str) -> None:
            try:
                payload = self._read_json()
                result = service.claim_stage(
                    job_id,
                    stage,
                    command_id=_optional_str(payload.get("command_id")),
                    attempt=_optional_int(payload.get("attempt")),
                    worker_id=_optional_str(payload.get("worker_id")),
                    idempotency_key=_optional_str(payload.get("idempotency_key")),
                    lease_seconds=_optional_int(payload.get("lease_seconds")),
                    max_attempts=_optional_int(payload.get("max_attempts")),
                )
                self._write_json(200, result)
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})
            except ValueError as exc:
                self._write_json(400, {"status": "bad_request", "error": str(exc)})

        def _heartbeat_stage(self, job_id: str, stage: str) -> None:
            try:
                payload = self._read_json()
                result = service.heartbeat_stage(
                    job_id,
                    stage,
                    claim_id=_optional_str(payload.get("claim_id")),
                    progress=_optional_float(payload.get("progress")),
                    lease_seconds=_optional_int(payload.get("lease_seconds")),
                )
                self._write_json(200, result)
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})
            except ValueError as exc:
                self._write_json(400, {"status": "bad_request", "error": str(exc)})

        def _handle_event(self) -> None:
            try:
                command = service.handle_event(self._read_json())
            except (KeyError, ValueError, JobNotFoundError) as exc:
                self._write_json(400, {"status": "bad_request", "error": str(exc)})
                return

            payload: dict[str, object] = {"status": "accepted", "published": command is not None}
            if command is not None:
                payload["queue"] = command.queue
                payload["published_command"] = command.message
            self._write_json(202, payload)

        def _reconcile_stale_leases(self) -> None:
            try:
                payload = self._read_json()
                result = service.reconcile_stale_leases(
                    retry_backoff_seconds=_optional_int(payload.get("retry_backoff_seconds")) or 0
                )
            except ValueError as exc:
                self._write_json(400, {"status": "bad_request", "error": str(exc)})
                return
            self._write_json(200, result)

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            if not raw:
                return {}
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("request body must be a JSON object")
            return decoded

        def _write_json(self, code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, code: int, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return JobServiceHandler


def serve_api(config: AppConfig, service: JobService, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(config, service))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _filters(query: str) -> dict[str, str]:
    parsed = parse_qs(query, keep_blank_values=False)
    allowed = {"status", "input_type", "current_stage", "user_id"}
    return {key: values[-1] for key, values in parsed.items() if key in allowed and values}


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>File Translation Admin</title>
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; color: #16202a; background: #f7f8fa; }
    header { padding: 16px 24px; background: #ffffff; border-bottom: 1px solid #d8dee6; }
    main { display: grid; grid-template-columns: minmax(320px, 420px) 1fr; gap: 16px; padding: 16px; }
    section { background: #ffffff; border: 1px solid #d8dee6; border-radius: 6px; min-width: 0; }
    .stack { display: grid; gap: 16px; min-width: 0; }
    h1 { margin: 0; font-size: 20px; }
    h2 { margin: 0; padding: 14px 16px; font-size: 15px; border-bottom: 1px solid #e3e8ef; }
    button, select { font: inherit; }
    .toolbar { display: flex; gap: 8px; padding: 12px 16px; border-bottom: 1px solid #e3e8ef; }
    .jobs { width: 100%; border-collapse: collapse; font-size: 13px; }
    .jobs th, .jobs td { padding: 9px 10px; border-bottom: 1px solid #edf0f5; text-align: left; }
    .jobs button { width: 100%; text-align: left; border: 0; background: transparent; color: #0f4d7a; cursor: pointer; }
    .detail { padding: 16px; display: grid; gap: 14px; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .field { border: 1px solid #e3e8ef; border-radius: 6px; padding: 10px; min-width: 0; }
    .label { color: #607080; font-size: 12px; }
    .value { font-size: 14px; overflow-wrap: anywhere; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f6f8; border: 1px solid #e3e8ef; border-radius: 6px; padding: 12px; }
    .danger { border: 1px solid #bf2f24; background: #fff5f3; color: #8c1d16; border-radius: 5px; padding: 8px 10px; cursor: pointer; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; } .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header><h1>File Translation Admin</h1></header>
  <main>
    <section>
      <h2>Jobs</h2>
      <div class="toolbar">
        <select id="status">
          <option value="">all</option>
          <option value="running">running</option>
          <option value="failed">failed</option>
          <option value="cancel_requested">cancel requested</option>
          <option value="cancelled">cancelled</option>
          <option value="completed">completed</option>
        </select>
        <button id="refresh">Refresh</button>
      </div>
      <table class="jobs">
        <thead><tr><th>Job</th><th>Type</th><th>Status</th><th>Stage</th></tr></thead>
        <tbody id="jobs"></tbody>
      </table>
    </section>
    <div class="stack">
      <section>
        <h2>System</h2>
        <div class="detail" id="system">Loading system health.</div>
      </section>
      <section>
        <h2>Detail</h2>
        <div class="detail" id="detail">Select a job.</div>
      </section>
    </div>
  </main>
  <script>
    const jobsBody = document.getElementById("jobs");
    const detail = document.getElementById("detail");
    const system = document.getElementById("system");
    const statusSelect = document.getElementById("status");

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]);
    }

    async function loadSystem() {
      const [health, queues, workers, failed] = await Promise.all([
        fetch("/admin/health").then((res) => res.json()),
        fetch("/admin/queues").then((res) => res.json()),
        fetch("/admin/workers").then((res) => res.json()),
        fetch("/admin/jobs?status=failed").then((res) => res.json())
      ]);
      const deps = health.dependencies || {};
      const dependencyRows = Object.entries(deps).map(([name, item]) =>
        `<div class="field"><div class="label">${escapeHtml(name)}</div><div class="value">${escapeHtml(item.status)}</div></div>`
      ).join("");
      const workerItems = (workers.workers || []).slice(0, 6).map((item) =>
        `${item.handled_stage}:${item.status}`
      ).join(", ");
      system.innerHTML = `
        <div class="grid">
          <div class="field"><div class="label">system</div><div class="value">${escapeHtml(health.overall_status)}</div></div>
          <div class="field"><div class="label">queues</div><div class="value">${escapeHtml(queues.status)}</div></div>
          <div class="field"><div class="label">failed jobs</div><div class="value">${escapeHtml(failed.count)}</div></div>
          ${dependencyRows}
        </div>
        <pre>${escapeHtml(workerItems || workers.note || "No worker stage data yet.")}</pre>
      `;
    }

    async function loadJobs() {
      await loadSystem();
      const status = statusSelect.value;
      const url = status ? `/admin/jobs?status=${encodeURIComponent(status)}` : "/admin/jobs";
      const payload = await fetch(url).then((res) => res.json());
      jobsBody.innerHTML = "";
      for (const job of payload.jobs) {
        const row = document.createElement("tr");
        row.innerHTML = `<td><button data-job="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id)}</button></td><td>${escapeHtml(job.input_type)}</td><td>${escapeHtml(job.status)}</td><td>${escapeHtml(job.current_stage)}</td>`;
        jobsBody.appendChild(row);
      }
    }

    async function loadDetail(jobId) {
      const payload = await fetch(`/admin/jobs/${encodeURIComponent(jobId)}`).then((res) => res.json());
      const job = payload.job;
      detail.innerHTML = `
        <div class="grid">
          <div class="field"><div class="label">input_type</div><div class="value">${escapeHtml(job.input_type)}</div></div>
          <div class="field"><div class="label">status</div><div class="value">${escapeHtml(job.status)}</div></div>
          <div class="field"><div class="label">current_stage</div><div class="value">${escapeHtml(job.current_stage)}</div></div>
          <div class="field"><div class="label">error_stage</div><div class="value">${escapeHtml(job.error_stage)}</div></div>
          <div class="field"><div class="label">error_message</div><div class="value">${escapeHtml(job.error_message)}</div></div>
          <div class="field"><div class="label">email_report</div><div class="value">${escapeHtml(job.artifacts.email_report)}</div></div>
        </div>
        <button class="danger" id="cancel">Cancel</button>
        <h2>Stages</h2><pre>${escapeHtml(JSON.stringify(payload.stages, null, 2))}</pre>
        <h2>Artifacts</h2><pre>${escapeHtml(JSON.stringify(payload.artifacts, null, 2))}</pre>
      `;
      document.getElementById("cancel").onclick = async () => {
        await fetch(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
        await loadDetail(jobId);
        await loadJobs();
      };
    }

    jobsBody.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-job]");
      if (button) loadDetail(button.dataset.job);
    });
    document.getElementById("refresh").onclick = loadJobs;
    statusSelect.onchange = loadJobs;
    loadJobs();
  </script>
</body>
</html>
"""
