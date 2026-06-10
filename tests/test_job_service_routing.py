from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "job-service"))

from ft_common.config import load_config
from job_service.orchestrator import JobService
from job_service.publisher import InMemoryCommandPublisher
from job_service.repository import InMemoryJobRepository
from job_service.routes import initial_stage


class JobServiceRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("job-service", "api", env={})
        self.publisher = InMemoryCommandPublisher(self.config)
        self.service = JobService(InMemoryJobRepository(), self.publisher)

    def create_job(self, input_type: str = "pdf"):
        return self.service.create_job(
            user_id="12345678",
            input_type=input_type,
            source_lang="en",
            target_lang="ko",
            original_filename=f"sample.{input_type}",
            file_id="a8f3k2p9",
            job_id=f"job-{input_type}",
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
        self.assertEqual(command.message["source_lang"], "en")
        self.assertEqual(command.message["target_lang"], "ko")

    def test_create_job_publishes_first_command_for_docx(self) -> None:
        job, command = self.create_job("docx")

        self.assertEqual(job.current_stage, "docx_extract")
        self.assertNotIn("pdf2docx", job.pipeline_route)
        self.assertEqual(command.queue, "q.commands.docx_extract")

    def test_create_job_publishes_first_command_for_hwpx(self) -> None:
        job, command = self.create_job("hwpx")

        self.assertEqual(job.current_stage, "hwpx_extract")
        self.assertNotIn("docx_extract", job.pipeline_route)
        self.assertEqual(command.queue, "q.commands.hwpx_extract")

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
        self.assertEqual(next_command.queue, "q.commands.pdf2docx")
        self.assertEqual(job.current_stage, "docx_extract")
        self.assertEqual(job.stages["pdf2docx"].status, "completed")
        self.assertEqual(job.artifacts["converted_docx"], "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx")

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


if __name__ == "__main__":
    unittest.main()
