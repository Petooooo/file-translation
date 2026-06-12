from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "job-service"))

from ft_common.config import load_config
from job_service.api import make_handler
from job_service.orchestrator import JobService
from job_service.publisher import InMemoryCommandPublisher
from job_service.repository import InMemoryJobRepository


class JobServiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("job-service", "api", env={})
        self.publisher = InMemoryCommandPublisher(self.config)
        self.service = JobService(InMemoryJobRepository(), self.publisher)
        handler = make_handler(self.config, self.service)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def create_job(self, input_type: str = "docx") -> str:
        payload = self.request(
            "POST",
            "/jobs",
            {
                "user_id": "12345678",
                "input_type": input_type,
                "source_lang": "en",
                "target_lang": "ko",
                "original_filename": f"sample.{input_type}",
                "file_id": f"api{input_type}",
                "input_object_key": f"2026-01-21/12345678/api{input_type}/input/original.{input_type}",
            },
        )
        return str(payload["job"]["job_id"])

    def test_admin_and_job_views_expose_stages_artifacts_and_html(self) -> None:
        job_id = self.create_job("docx")
        self.request(
            "POST",
            "/events",
            {
                "event_type": "translate.progress",
                "job_id": job_id,
                "input_type": "docx",
                "stage": "docx_translate",
                "total_units": 3,
                "translated_units": 1,
                "failed_units": 0,
            },
        )
        self.request(
            "POST",
            "/events",
            {
                "event_type": "stage.completed",
                "job_id": job_id,
                "input_type": "docx",
                "stage": "docx_extract",
                "outputs": {"text_units": "2026-01-21/12345678/apidocx/02_extract/text_units.json"},
            },
        )

        job_payload = self.request("GET", f"/jobs/{job_id}")
        stages_payload = self.request("GET", f"/jobs/{job_id}/stages")
        artifacts_payload = self.request("GET", f"/jobs/{job_id}/artifacts")
        admin_list = self.request("GET", "/admin/jobs?status=running")
        admin_detail = self.request("GET", f"/admin/jobs/{job_id}")

        self.assertEqual(job_payload["current_stage"], "docx_translate")
        self.assertEqual(job_payload["progress"]["translated_units"], 1)
        self.assertEqual(stages_payload["stages"][0]["stage"], "receive_input")
        self.assertTrue(any(stage["stage"] == "docx_extract" for stage in stages_payload["stages"]))
        self.assertTrue(any(item["artifact_type"] == "text_units" for item in artifacts_payload["artifacts"]))
        self.assertEqual(admin_list["count"], 1)
        self.assertEqual(admin_list["jobs"][0]["job_id"], job_id)
        self.assertEqual(admin_detail["job"]["job_id"], job_id)
        self.assertTrue(any(item["artifact_type"] == "text_units" for item in admin_detail["artifacts"]))

        with urlopen(f"{self.base_url}/admin", timeout=5) as response:
            html = response.read().decode("utf-8")
        self.assertIn("File Translation Admin", html)
        self.assertIn("/admin/jobs", html)
        self.assertIn("/admin/health", html)
        self.assertNotIn("q.commands", html)
        self.assertNotIn("RABBITMQ_PASSWORD", html)

    def test_monitoring_endpoints_report_default_readiness(self) -> None:
        ready = self.request("GET", "/readyz")
        health = self.request("GET", "/admin/health")
        workers = self.request("GET", "/admin/workers")
        queues = self.request("GET", "/admin/queues")

        self.assertEqual(ready["status"], "ok")
        self.assertEqual(ready["overall_status"], "healthy")
        self.assertEqual(health["overall_status"], "healthy")
        self.assertEqual(health["dependencies"]["postgresql"]["status"], "skipped")
        self.assertEqual(health["dependencies"]["rabbitmq"]["status"], "skipped")
        self.assertEqual(health["dependencies"]["minio"]["status"], "skipped")
        self.assertFalse(workers["heartbeat_available"])
        self.assertEqual(workers["source"], "job_stage_events")
        self.assertEqual(queues["status"], "skipped")
        self.assertTrue(any(queue["name"] == "q.commands.pdf2docx" for queue in queues["queues"]))

    def test_cancel_api_updates_admin_filterable_state(self) -> None:
        job_id = self.create_job("hwpx")

        cancelled = self.request("POST", f"/jobs/{job_id}/cancel")
        admin_list = self.request("GET", "/admin/jobs?status=cancel_requested")

        self.assertEqual(cancelled["status"], "cancel_requested")
        self.assertEqual(admin_list["count"], 1)
        self.assertEqual(admin_list["jobs"][0]["current_stage"], "hwpx_extract")

    def test_retry_failed_job_republishes_failed_stage(self) -> None:
        job_id = self.create_job("pdf")
        self.request(
            "POST",
            "/events",
            {
                "event_type": "stage.failed",
                "job_id": job_id,
                "input_type": "pdf",
                "stage": "pdf2docx",
                "error_message": "converter failed",
            },
        )

        retried = self.request("POST", f"/jobs/{job_id}/retry")

        self.assertEqual(retried["job"]["status"], "running")
        self.assertEqual(retried["job"]["current_stage"], "pdf2docx")
        self.assertEqual(retried["queue"], "q.commands.pdf2docx")
        self.assertEqual(retried["published_command"]["attempt"], 2)

    def test_retry_running_job_returns_conflict(self) -> None:
        job_id = self.create_job("docx")
        request = Request(f"{self.base_url}/jobs/{job_id}/retry", data=b"{}", method="POST")

        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)

        self.assertEqual(context.exception.code, 409)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "retry_not_allowed")

    def test_stage_claim_and_heartbeat_api(self) -> None:
        payload = self.request(
            "POST",
            "/jobs",
            {
                "user_id": "12345678",
                "input_type": "pdf",
                "source_lang": "en",
                "target_lang": "ko",
                "original_filename": "sample.pdf",
                "file_id": "apiclaim",
                "input_object_key": "2026-01-21/12345678/apiclaim/input/original.pdf",
            },
        )
        job_id = str(payload["job"]["job_id"])
        command = payload["published_command"]

        claim = self.request(
            "POST",
            f"/jobs/{job_id}/stages/pdf2docx/claim",
            {
                "command_id": command["command_id"],
                "attempt": command["attempt"],
                "worker_id": "pdf2docx-worker:pdf2docx",
                "idempotency_key": command["idempotency_key"],
                "lease_seconds": 300,
                "max_attempts": 3,
            },
        )
        duplicate = self.request(
            "POST",
            f"/jobs/{job_id}/stages/pdf2docx/claim",
            {
                "command_id": command["command_id"],
                "attempt": command["attempt"],
                "worker_id": "pdf2docx-worker:pdf2docx",
                "idempotency_key": command["idempotency_key"],
            },
        )
        heartbeat = self.request(
            "POST",
            f"/jobs/{job_id}/stages/pdf2docx/heartbeat",
            {"claim_id": claim["claim_id"], "progress": 42},
        )
        job = self.request("GET", f"/jobs/{job_id}")

        self.assertEqual(claim["claim_status"], "CLAIMED")
        self.assertTrue(claim["should_process"])
        self.assertEqual(duplicate["claim_status"], "ALREADY_RUNNING")
        self.assertFalse(duplicate["should_process"])
        self.assertEqual(heartbeat["claim_status"], "CLAIMED")
        self.assertEqual(job["stages"]["pdf2docx"]["progress"], 42)
        self.assertIsNotNone(job["stages"]["pdf2docx"]["lease_until"])

    def test_internal_reconcile_stale_leases_api_republishes_retry_command(self) -> None:
        payload = self.request(
            "POST",
            "/jobs",
            {
                "user_id": "12345678",
                "input_type": "pdf",
                "source_lang": "en",
                "target_lang": "ko",
                "original_filename": "sample.pdf",
                "file_id": "apistale",
                "input_object_key": "2026-01-21/12345678/apistale/input/original.pdf",
            },
        )
        job_id = str(payload["job"]["job_id"])
        command = payload["published_command"]
        self.request(
            "POST",
            f"/jobs/{job_id}/stages/pdf2docx/claim",
            {
                "command_id": command["command_id"],
                "attempt": command["attempt"],
                "worker_id": "pdf2docx-worker:pdf2docx",
                "idempotency_key": command["idempotency_key"],
                "lease_seconds": -1,
                "max_attempts": 3,
            },
        )

        reconciled = self.request("POST", "/internal/reconcile/stale-leases")
        job = self.request("GET", f"/jobs/{job_id}")

        self.assertEqual(reconciled["status"], "reconciled")
        self.assertEqual(reconciled["stale_stages"], 1)
        self.assertEqual(reconciled["retried"], 1)
        self.assertEqual(reconciled["published_commands"][0]["message"]["stage"], "pdf2docx")
        self.assertEqual(reconciled["published_commands"][0]["message"]["attempt"], 2)
        self.assertEqual(job["stages"]["pdf2docx"]["attempts"], 2)
        self.assertEqual(job["stages"]["pdf2docx"]["last_reconcile_reason"], "stale_lease_expired")

    def test_readyz_reports_unhealthy_when_required_dependency_fails(self) -> None:
        bad_config = load_config(
            "job-service",
            "api",
            env={
                "JOB_SERVICE_COMMAND_PUBLISHER": "rabbitmq",
                "RABBITMQ_HOST": "127.0.0.1",
                "RABBITMQ_PORT": "9",
            },
        )
        service = JobService(InMemoryJobRepository(), InMemoryCommandPublisher(bad_config))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bad_config, service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as context:
                urlopen(f"http://127.0.0.1:{server.server_port}/readyz", timeout=5)
            self.assertEqual(context.exception.code, 503)
            payload = json.loads(context.exception.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(payload["status"], "unhealthy")
        self.assertEqual(payload["overall_status"], "unhealthy")
        self.assertEqual(payload["dependencies"]["rabbitmq"]["status"], "unhealthy")


if __name__ == "__main__":
    unittest.main()
