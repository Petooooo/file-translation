"""Tiny stdlib HTTP API for job-service routing skeleton."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse

from ft_common.config import AppConfig
from ft_common.health import health_payload
from job_service.orchestrator import JobService
from job_service.repository import JobNotFoundError


def make_handler(config: AppConfig, service: JobService) -> type[BaseHTTPRequestHandler]:
    class JobServiceHandler(BaseHTTPRequestHandler):
        server_version = "file-translation-job-service/0.1"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            static_routes: dict[str, Callable[[], tuple[int, dict[str, object]]]] = {
                "/healthz": lambda: (200, health_payload(config)),
                "/readyz": lambda: (200, health_payload(config)),
                "/config": lambda: (200, config.safe_dict()),
            }
            if path in static_routes:
                code, payload = static_routes[path]()
                self._write_json(code, payload)
                return

            parts = _parts(path)
            if len(parts) == 2 and parts[0] == "jobs":
                self._write_job(parts[1])
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
            if parts == ["events"]:
                self._handle_event()
                return

            self._write_json(404, {"status": "not_found", "path": path})

        def log_message(self, format: str, *args: object) -> None:
            return

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

        def _cancel_job(self, job_id: str) -> None:
            try:
                self._write_json(200, service.cancel_job(job_id).to_dict())
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

        def _write_sendability(self, job_id: str) -> None:
            try:
                self._write_json(200, service.sendability(job_id))
            except JobNotFoundError:
                self._write_json(404, {"status": "not_found", "job_id": job_id})

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

    return JobServiceHandler


def serve_api(config: AppConfig, service: JobService, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(config, service))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
