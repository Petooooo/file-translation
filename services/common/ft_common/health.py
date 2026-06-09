"""HTTP health server for the job-service skeleton."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from ft_common.config import AppConfig


def health_payload(config: AppConfig, status: str = "ok") -> dict[str, object]:
    return {
        "status": status,
        "service": config.service_name,
        "environment": config.app_env,
        "namespace": config.namespace,
    }


def make_handler(config: AppConfig) -> type[BaseHTTPRequestHandler]:
    class HealthHandler(BaseHTTPRequestHandler):
        server_version = "file-translation-health/0.1"

        def do_GET(self) -> None:
            routes: dict[str, Callable[[], tuple[int, dict[str, object]]]] = {
                "/healthz": lambda: (200, health_payload(config)),
                "/readyz": lambda: (200, health_payload(config)),
                "/config": lambda: (200, config.safe_dict()),
            }
            handler = routes.get(self.path)
            if handler is None:
                self._write_json(404, {"status": "not_found", "path": self.path})
                return

            code, payload = handler()
            self._write_json(code, payload)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _write_json(self, code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HealthHandler


def serve_health(config: AppConfig, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(config))
    try:
        server.serve_forever()
    finally:
        server.server_close()
