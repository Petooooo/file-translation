from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "job-service"))

from ft_common.config import load_config
from job_service.models import Job
from job_service.orchestrator import JobService
from job_service.publisher import InMemoryCommandPublisher
from job_service.repository import InMemoryJobRepository
from job_service.routes import initial_stage


class JobServiceRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("job-service", "api", env={})
        self.publisher = InMemoryCommandPublisher(self.config)
        self.service = JobService(InMemoryJobRepository(), self.publisher)

    def create_job(self, input_type: str = "pdf", *, job_id: str | None = None, file_id: str = "a8f3k2p9"):
        return self.service.create_job(
            user_id="12345678",
            input_type=input_type,
            source_lang="en",
            target_lang="ko",
            original_filename=f"sample.{input_type}",
            file_id=file_id,
            job_id=job_id or f"job-{input_type}",
            today=date(2026, 1, 21),
        )

    def test_initial_stage_by_input_type(self) -> None:
        self.assertEqual(initial_stage("pdf"), "pdf2docx")
        self.assertEqual(initial_stage("docx"), "docx_extract")
        self.assertEqual(initial_stage("hwpx"), "hwpx_extract")

    def test_create_job_publishes_first_command_for_pdf(self) -> None:
        job, command = self.create_job("pdf")

        self.assertEqual(job.input_type, "pdf")
        self.assertEqual(job.status, "running")
        self.assertEqual(job.current_stage, "pdf2docx")
        self.assertEqual(job.object_prefix, "2026-01-21/12345678/a8f3k2p9")
        self.assertEqual(job.input_object_key, "2026-01-21/12345678/a8f3k2p9/input/original.pdf")
        self.assertEqual(command.queue, "q.commands.pdf2docx")
        self.assertEqual(command.message["stage"], "pdf2docx")
        self.assertEqual(command.message["attempt"], 1)
        self.assertEqual(command.message["command_id"], f"{job.job_id}:pdf2docx:1")
        self.assertEqual(command.message["idempotency_key"], f"{job.job_id}:pdf2docx:1")
        self.assertEqual(command.message["lease_seconds"], 300)
        self.assertEqual(command.message["max_attempts"], 3)
        self.assertEqual(command.message["source_lang"], "en")
        self.assertEqual(command.message["target_lang"], "ko")
        self.assertEqual(command.message["input_object_key"], job.input_object_key)

    def test_job_model_round_trips_through_json_payload(self) -> None:
        job, _ = self.create_job("hwpx")
        job.stages["hwpx_extract"].outputs["text_units"] = "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json"
        job.artifacts["text_units"] = job.stages["hwpx_extract"].outputs["text_units"]

        restored = Job.from_dict(job.to_dict())

        self.assertEqual(restored.job_id, job.job_id)
        self.assertEqual(restored.current_stage, "hwpx_extract")
        self.assertEqual(restored.created_at.isoformat(), job.created_at.isoformat())
        self.assertEqual(restored.stages["hwpx_extract"].outputs["text_units"], job.artifacts["text_units"])

    def test_create_job_publishes_first_command_for_docx(self) -> None:
        job, command = self.create_job("docx")

        self.assertEqual(job.current_stage, "docx_extract")
        self.assertNotIn("pdf2docx", job.pipeline_route)
        self.assertEqual(command.queue, "q.commands.docx_extract")
        self.assertEqual(command.message["input_object_key"], job.input_object_key)

    def test_create_job_publishes_first_command_for_hwpx(self) -> None:
        job, command = self.create_job("hwpx")

        self.assertEqual(job.current_stage, "hwpx_extract")
        self.assertNotIn("docx_extract", job.pipeline_route)
        self.assertEqual(command.queue, "q.commands.hwpx_extract")
        self.assertEqual(command.message["input_object_key"], job.input_object_key)

    def test_invalid_input_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.create_job("txt")

    def test_stage_completed_event_publishes_next_route_stage(self) -> None:
        job, next_command = self.create_job("pdf")

        command = self.service.handle_event(
            {
                "event_type": "stage.completed",
                "job_id": job.job_id,
                "input_type": "pdf",
                "stage": "pdf2docx",
                "outputs": {
                    "converted_docx": "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx",
                },
            }
        )

        self.assertIsNotNone(command)
        self.assertEqual(command.queue, "q.commands.docx_extract")
        self.assertEqual(command.message["stage"], "docx_extract")
        self.assertNotIn("input_object_key", command.message)
        self.assertEqual(next_command.queue, "q.commands.pdf2docx")
        self.assertEqual(job.current_stage, "docx_extract")
        self.assertEqual(job.stages["pdf2docx"].status, "completed")
        self.assertEqual(job.artifacts["converted_docx"], "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx")

    def test_stage_claim_records_lease_and_duplicate_noops(self) -> None:
        job, command = self.create_job("pdf")

        claim = self.service.claim_stage(
            job.job_id,
            "pdf2docx",
            command_id=str(command.message["command_id"]),
            attempt=1,
            worker_id="pdf2docx-worker:pdf2docx",
            idempotency_key=str(command.message["idempotency_key"]),
        )
        duplicate = self.service.claim_stage(
            job.job_id,
            "pdf2docx",
            command_id=str(command.message["command_id"]),
            attempt=1,
            worker_id="pdf2docx-worker:pdf2docx",
            idempotency_key=str(command.message["idempotency_key"]),
        )
        heartbeat = self.service.heartbeat_stage(
            job.job_id,
            "pdf2docx",
            claim_id=str(claim["claim_id"]),
            progress=17,
        )

        stage = self.service.get_job(job.job_id).stages["pdf2docx"]
        self.assertEqual(claim["claim_status"], "CLAIMED")
        self.assertTrue(claim["should_process"])
        self.assertEqual(duplicate["claim_status"], "ALREADY_RUNNING")
        self.assertFalse(duplicate["should_process"])
        self.assertEqual(heartbeat["claim_status"], "CLAIMED")
        self.assertEqual(stage.claim_id, command.message["command_id"])
        self.assertIsNotNone(stage.lease_until)
        self.assertIsNotNone(stage.last_heartbeat_at)
        self.assertEqual(stage.progress, 17)

    def test_duplicate_completed_event_does_not_publish_next_command_twice(self) -> None:
        job, command = self.create_job("pdf")
        claim = self.service.claim_stage(
            job.job_id,
            "pdf2docx",
            command_id=str(command.message["command_id"]),
            attempt=1,
            worker_id="pdf2docx-worker:pdf2docx",
            idempotency_key=str(command.message["idempotency_key"]),
        )
        event = {
            "event_type": "stage.completed",
            "job_id": job.job_id,
            "input_type": "pdf",
            "stage": "pdf2docx",
            "attempt": 1,
            "command_id": command.message["command_id"],
            "claim_id": claim["claim_id"],
        }

        first = self.service.handle_event(event)
        second = self.service.handle_event(event)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(self.publisher.published), 2)

    def test_claim_completed_cancelled_and_max_attempts_noop_or_fail(self) -> None:
        completed_job, command = self.create_job("docx")
        self.service.handle_event(
            {
                "event_type": "stage.completed",
                "job_id": completed_job.job_id,
                "input_type": "docx",
                "stage": "docx_extract",
            }
        )
        completed_claim = self.service.claim_stage(
            completed_job.job_id,
            "docx_extract",
            command_id=str(command.message["command_id"]),
            attempt=1,
        )
        self.assertEqual(completed_claim["claim_status"], "ALREADY_COMPLETED")
        self.assertFalse(completed_claim["should_process"])

        cancelled_job, cancelled_command = self.create_job("hwpx")
        self.service.cancel_job(cancelled_job.job_id)
        cancelled_claim = self.service.claim_stage(
            cancelled_job.job_id,
            "hwpx_extract",
            command_id=str(cancelled_command.message["command_id"]),
            attempt=1,
        )
        self.assertEqual(cancelled_claim["claim_status"], "JOB_CANCELLED")
        self.assertFalse(cancelled_claim["should_process"])

        exhausted_job, exhausted_command = self.create_job("pdf")
        exhausted_claim = self.service.claim_stage(
            exhausted_job.job_id,
            "pdf2docx",
            command_id=str(exhausted_command.message["command_id"]),
            attempt=4,
            max_attempts=3,
        )
        self.assertEqual(exhausted_claim["claim_status"], "MAX_ATTEMPTS_EXCEEDED")
        self.assertEqual(self.service.get_job(exhausted_job.job_id).status, "failed")

    def test_reconcile_stale_lease_retries_and_ignores_late_previous_attempt_event(self) -> None:
        job, command = self.create_job("pdf", job_id="job-pdf-stale", file_id="stalepdf")
        claim = self.service.claim_stage(
            job.job_id,
            "pdf2docx",
            command_id=str(command.message["command_id"]),
            attempt=1,
            worker_id="pdf2docx-worker:pdf2docx",
            idempotency_key=str(command.message["idempotency_key"]),
            lease_seconds=-1,
        )

        result = self.service.reconcile_stale_leases()
        published_commands = result["published_commands"]

        self.assertEqual(claim["claim_status"], "CLAIMED")
        self.assertEqual(result["stale_stages"], 1)
        self.assertEqual(result["retried"], 1)
        self.assertEqual(published_commands[0]["message"]["stage"], "pdf2docx")
        self.assertEqual(published_commands[0]["message"]["attempt"], 2)

        stale_event = self.service.handle_event(
            {
                "event_type": "stage.completed",
                "job_id": job.job_id,
                "input_type": "pdf",
                "stage": "pdf2docx",
                "attempt": 1,
                "claim_id": claim["claim_id"],
                "command_id": claim["command_id"],
            }
        )
        current = self.service.get_job(job.job_id)
        state = current.stages["pdf2docx"]

        self.assertIsNone(stale_event)
        self.assertEqual(current.status, "running")
        self.assertEqual(current.current_stage, "pdf2docx")
        self.assertEqual(state.status, "running")
        self.assertEqual(state.attempts, 2)
        self.assertEqual(state.stale_attempts, 1)
        self.assertEqual(state.last_reconcile_reason, "stale_lease_expired")
        self.assertIsNone(state.command_id)
        self.assertEqual(len(self.publisher.published), 2)

    def test_reconcile_stale_lease_fails_when_max_attempts_are_exhausted(self) -> None:
        job, _ = self.create_job("pdf", job_id="job-pdf-max", file_id="stalemax")
        claim = self.service.claim_stage(
            job.job_id,
            "pdf2docx",
            command_id="job-pdf-max:pdf2docx:3",
            attempt=3,
            worker_id="pdf2docx-worker:pdf2docx",
            idempotency_key="job-pdf-max:pdf2docx:3",
            lease_seconds=-1,
            max_attempts=3,
        )

        result = self.service.reconcile_stale_leases()
        current = self.service.get_job(job.job_id)
        state = current.stages["pdf2docx"]

        self.assertEqual(claim["claim_status"], "CLAIMED")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["retried"], 0)
        self.assertEqual(current.status, "failed")
        self.assertEqual(current.current_stage, "failed")
        self.assertEqual(current.error_stage, "pdf2docx")
        self.assertEqual(state.last_reconcile_reason, "max_attempts_exceeded")
        self.assertTrue(state.lease_expired)

    def test_reconcile_stale_cancelled_job_does_not_retry(self) -> None:
        job, command = self.create_job("hwpx", job_id="job-hwpx-cancel-stale", file_id="stalecancel")
        self.service.claim_stage(
            job.job_id,
            "hwpx_extract",
            command_id=str(command.message["command_id"]),
            attempt=1,
            worker_id="hwpx-worker:hwpx_extract",
            idempotency_key=str(command.message["idempotency_key"]),
            lease_seconds=-1,
        )
        self.service.cancel_job(job.job_id)

        result = self.service.reconcile_stale_leases()
        current = self.service.get_job(job.job_id)
        state = current.stages["hwpx_extract"]

        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(result["retried"], 0)
        self.assertEqual(current.status, "cancelled")
        self.assertEqual(current.current_stage, "cancelled")
        self.assertEqual(state.status, "cancelled")
        self.assertEqual(state.last_reconcile_reason, "job_cancelled_no_retry")

    def test_reconcile_stale_email_send_fails_without_republishing(self) -> None:
        job, _ = self.create_job("hwpx", job_id="job-hwpx-email-stale", file_id="staleemail")
        response = None
        for stage in ["hwpx_extract", "hwpx_translate", "hwpx_replace", "hwpx_export"]:
            response = self.service.handle_event(
                {
                    "event_type": "stage.completed",
                    "job_id": job.job_id,
                    "input_type": "hwpx",
                    "stage": stage,
                }
            )
        self.assertIsNotNone(response)
        email_command = response.message
        self.service.claim_stage(
            job.job_id,
            "email_send",
            command_id=str(email_command["command_id"]),
            attempt=int(email_command["attempt"]),
            worker_id="email-worker:email_send",
            idempotency_key=str(email_command["idempotency_key"]),
            lease_seconds=-1,
        )

        published_before = len(self.publisher.published)
        result = self.service.reconcile_stale_leases()
        current = self.service.get_job(job.job_id)
        state = current.stages["email_send"]

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["retried"], 0)
        self.assertEqual(len(self.publisher.published), published_before)
        self.assertEqual(current.status, "failed")
        self.assertEqual(current.error_stage, "email_send")
        self.assertEqual(state.last_reconcile_reason, "email_send_stale_no_auto_retry")
        self.assertTrue(state.lease_expired)

    def test_cancel_requested_job_does_not_publish_next_command(self) -> None:
        job, _ = self.create_job("docx")
        self.service.cancel_job(job.job_id)

        command = self.service.handle_event(
            {
                "event_type": "stage.completed",
                "job_id": job.job_id,
                "input_type": "docx",
                "stage": "docx_extract",
            }
        )

        self.assertIsNone(command)
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(job.current_stage, "cancelled")
        self.assertEqual(len(self.publisher.published), 1)

    def test_progress_and_artifacts_are_returned_from_job_query(self) -> None:
        job, _ = self.create_job("hwpx")

        self.service.handle_event(
            {
                "event_type": "translate.progress",
                "job_id": job.job_id,
                "input_type": "hwpx",
                "stage": "hwpx_translate",
                "total_units": 10,
                "translated_units": 4,
                "failed_units": 0,
            }
        )
        self.service.handle_event(
            {
                "event_type": "stage.completed",
                "job_id": job.job_id,
                "input_type": "hwpx",
                "stage": "hwpx_extract",
                "outputs": {
                    "text_units": "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json",
                },
            }
        )

        payload = self.service.get_job(job.job_id).to_dict()
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["current_stage"], "hwpx_translate")
        self.assertEqual(payload["artifacts"]["text_units"], "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(payload["progress"]["translated_units"], 4)

    def test_final_email_stage_completion_marks_job_completed(self) -> None:
        job, _ = self.create_job("hwpx")
        route = list(job.pipeline_route)

        for stage in route[:-1]:
            command = self.service.handle_event(
                {
                    "event_type": "stage.completed",
                    "job_id": job.job_id,
                    "input_type": "hwpx",
                    "stage": stage,
                }
            )
            self.assertIsNotNone(command)
            self.assertEqual(command.message["stage"], route[route.index(stage) + 1])

        self.assertEqual(job.current_stage, "email_send")
        self.assertTrue(self.service.sendability(job.job_id)["sendable"])

        command = self.service.handle_event(
            {
                "event_type": "stage.completed",
                "job_id": job.job_id,
                "input_type": "hwpx",
                "stage": "email_send",
            }
        )

        self.assertIsNone(command)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.current_stage, "completed")
        self.assertFalse(self.service.sendability(job.job_id)["sendable"])

    def test_sendability_returns_email_worker_job_details_and_artifacts(self) -> None:
        job, _ = self.create_job("docx")
        for stage, outputs in [
            ("docx_extract", {"text_units": "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json"}),
            ("docx_translate", {"translated_units": "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json"}),
            ("docx_replace", {"translated_docx": "2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx"}),
            (
                "docx_export",
                {
                    "final_docx": "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
                    "final_pdf": "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
                },
            ),
            ("docx_marker", {"marker_docx": "2026-01-21/12345678/a8f3k2p9/05_export/marker.docx"}),
            ("pdf2hwpx", {"final_hwpx": "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx"}),
        ]:
            self.service.handle_event(
                {
                    "event_type": "stage.completed",
                    "job_id": job.job_id,
                    "input_type": "docx",
                    "stage": stage,
                    "outputs": outputs,
                }
            )

        payload = self.service.sendability(job.job_id)

        self.assertTrue(payload["sendable"])
        self.assertEqual(payload["input_type"], "docx")
        self.assertEqual(payload["user_id"], "12345678")
        self.assertEqual(payload["object_prefix"], "2026-01-21/12345678/a8f3k2p9")
        self.assertEqual(payload["artifacts"]["final_docx"], "2026-01-21/12345678/a8f3k2p9/05_export/final.docx")
        self.assertEqual(payload["artifacts"]["final_pdf"], "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf")
        self.assertEqual(payload["artifacts"]["final_hwpx"], "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx")


if __name__ == "__main__":
    unittest.main()
