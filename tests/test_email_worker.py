from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "email-worker"))

from ft_common.config import load_config
from email_worker.artifacts import (
    EmailSendCommand,
    build_email_request,
    event_queue_key,
    process_email_send_command,
    stage_failed_event,
)
from email_worker.provider import MailSendResult


class FakeArtifactStore:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_reports: list[dict[str, object]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        raise AssertionError("email-worker mock flow should not download attachments")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        self.uploaded_reports.append(json.loads(source.read_text(encoding="utf-8")))


class FakeJobServiceClient:
    def __init__(self, sendability: dict[str, object]) -> None:
        self.sendability = sendability
        self.seen_job_ids: list[str] = []

    def get_sendability(self, job_id: str) -> dict[str, object]:
        self.seen_job_ids.append(job_id)
        return self.sendability


class RecordingMailProvider:
    name = "mock"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def send_mail(
        self,
        *,
        uid: str,
        to: str,
        subject: str,
        body: str,
        attachments: list[dict[str, object]],
        metadata: dict[str, object],
    ) -> MailSendResult:
        self.calls.append(
            {
                "uid": uid,
                "to": to,
                "subject": subject,
                "body": body,
                "attachments": attachments,
                "metadata": metadata,
            }
        )
        if self.fail:
            raise RuntimeError("mail API unavailable")
        return MailSendResult(
            provider="mock",
            status="sent",
            sent_at="2026-01-21T12:00:00Z",
            provider_message_id="mock-message-1",
        )


class EmailWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("email-worker", "worker", "email_send", env={})

    def test_email_send_command_accepts_minimal_contract_and_validates_stage(self) -> None:
        command = EmailSendCommand.from_message({"job_id": "job-1", "stage": "email_send"})

        self.assertEqual(command.job_id, "job-1")
        self.assertEqual(command.stage, "email_send")
        with self.assertRaises(ValueError):
            EmailSendCommand.from_message({"job_id": "job-1", "stage": "pdf2hwpx"})

    def test_build_email_request_uses_sendability_artifacts_and_local_recipient_fallback(self) -> None:
        command = EmailSendCommand.from_message({"job_id": "job-1", "stage": "email_send"})

        request_payload = build_email_request(command, _sendable_payload(), self.config)

        self.assertEqual(request_payload.uid, "12345678")
        self.assertEqual(request_payload.to, "12345678@example.local")
        self.assertEqual(request_payload.input_type, "docx")
        self.assertEqual(request_payload.report_object_key, "2026-01-21/12345678/a8f3k2p9/reports/email_report.json")
        self.assertEqual(
            [attachment["object_key"] for attachment in request_payload.attachments],
            [
                "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
                "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
                "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx",
            ],
        )

    def test_process_command_checks_sendability_uploads_report_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()
        provider = RecordingMailProvider()
        client = FakeJobServiceClient(_sendable_payload())

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_email_send_command(
                {"job_id": "job-1", "stage": "email_send"},
                store=store,
                work_root=Path(temp_dir),
                provider=provider,
                job_service_client=client,
                config=self.config,
            )

        self.assertEqual(client.seen_job_ids, ["job-1"])
        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(event["input_type"], "docx")
        self.assertEqual(
            event["outputs"],
            {"email_report": "2026-01-21/12345678/a8f3k2p9/reports/email_report.json"},
        )
        self.assertEqual(event["metrics"], {"provider": "mock"})
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/reports/email_report.json")
        self.assertEqual(store.uploads[0][2], "application/json")
        self.assertEqual(store.uploaded_reports[0]["provider"], "mock")
        self.assertEqual(store.uploaded_reports[0]["status"], "sent")
        self.assertNotIn("EMAIL_API_TOKEN", json.dumps(store.uploaded_reports[0]))

    def test_non_sendable_job_publishes_failed_event_without_provider_call(self) -> None:
        store = FakeArtifactStore()
        provider = RecordingMailProvider()
        client = FakeJobServiceClient(
            {
                **_sendable_payload(),
                "sendable": False,
                "status": "cancelled",
                "reason": "job is cancelled",
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_email_send_command(
                {"job_id": "job-1", "stage": "email_send"},
                store=store,
                work_root=Path(temp_dir),
                provider=provider,
                job_service_client=client,
                config=self.config,
            )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "EMAIL_NOT_SENDABLE")
        self.assertEqual(event["error_message"], "job is cancelled")
        self.assertEqual(provider.calls, [])
        self.assertEqual(store.uploads, [])

    def test_email_send_disabled_publishes_failed_event(self) -> None:
        disabled_config = load_config("email-worker", "worker", "email_send", env={"EMAIL_SEND_ENABLED": "false"})

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_email_send_command(
                {"job_id": "job-1", "stage": "email_send"},
                store=FakeArtifactStore(),
                work_root=Path(temp_dir),
                provider=RecordingMailProvider(),
                job_service_client=FakeJobServiceClient(_sendable_payload()),
                config=disabled_config,
            )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event["error_code"], "EMAIL_SEND_DISABLED")

    def test_provider_failure_uses_email_send_failed_contract(self) -> None:
        event = stage_failed_event(
            {"job_id": "job-1", "input_type": "docx", "stage": "email_send"},
            RuntimeError("mail API unavailable"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event["error_code"], "EMAIL_SEND_FAILED")
        self.assertEqual(event["error_message"], "mail API unavailable")


def _sendable_payload() -> dict[str, object]:
    return {
        "job_id": "job-1",
        "sendable": True,
        "status": "running",
        "current_stage": "email_send",
        "reason": None,
        "input_type": "docx",
        "user_id": "12345678",
        "file_id": "a8f3k2p9",
        "object_prefix": "2026-01-21/12345678/a8f3k2p9",
        "artifacts": {
            "final_docx": "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
            "final_pdf": "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
            "final_hwpx": "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx",
        },
    }


if __name__ == "__main__":
    unittest.main()
