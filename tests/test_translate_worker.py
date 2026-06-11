from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "translate-worker"))

from translate_worker.artifacts import (
    TranslateWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_translate_command,
    stage_failed_event,
)
from translate_worker.provider import MockTranslationProvider
from translate_worker.translation import translate_text_units


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_payloads: list[dict[str, object]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(_text_units_payload()), encoding="utf-8")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        self.uploaded_payloads.append(json.loads(source.read_text(encoding="utf-8")))


class TranslateWorkerTests(unittest.TestCase):
    def test_mock_provider_translates_units_and_reports_progress(self) -> None:
        progress: list[tuple[int, int, int]] = []

        payload = translate_text_units(
            _text_units_payload(),
            provider=MockTranslationProvider(),
            progress_callback=lambda total, translated, failed: progress.append((total, translated, failed)),
        )

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["job_id"], "job-1")
        self.assertEqual(payload["provider"], "mock")
        self.assertEqual(payload["source_lang"], "en")
        self.assertEqual(payload["target_lang"], "ko")
        self.assertEqual(
            payload["units"],
            [
                {
                    "uid": "unit-000001",
                    "source": "Hello world",
                    "translated": "[ko] Hello world",
                    "status": "translated",
                },
                {
                    "uid": "unit-000002",
                    "source": "Translate me",
                    "translated": "[ko] Translate me",
                    "status": "translated",
                },
            ],
        )
        self.assertEqual(progress, [(2, 1, 0), (2, 2, 0)])

    def test_worker_command_validates_route_stage_and_input_type(self) -> None:
        command = TranslateWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_translate",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "source_lang": "en",
                "target_lang": "ko",
            }
        )

        self.assertEqual(command.input_type, "pdf")
        hwpx_command = TranslateWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "hwpx",
                "stage": "hwpx_translate",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(hwpx_command.stage, "hwpx_translate")
        with self.assertRaises(ValueError):
            TranslateWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "docx_translate",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            TranslateWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "hwpx_translate",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_minio_contract_and_allow_overrides(self) -> None:
        command = TranslateWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_translate",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        override_command = TranslateWorkerCommand.from_message(
            {
                "job_id": "job-2",
                "input_type": "docx",
                "stage": "docx_translate",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "input_object_key": "custom/text_units.json",
                "output_object_key": "custom/translated_units.json",
            }
        )

        self.assertEqual(artifact_keys_for(command).text_units, "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(
            artifact_keys_for(command).translated_units,
            "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json",
        )
        self.assertEqual(artifact_keys_for(override_command).text_units, "custom/text_units.json")
        self.assertEqual(artifact_keys_for(override_command).translated_units, "custom/translated_units.json")

    def test_process_command_downloads_translates_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()
        progress_events: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_translate_command(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_translate",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                    "source_lang": "en",
                    "target_lang": "ko",
                },
                store=store,
                work_root=Path(temp_dir),
                provider=MockTranslationProvider(),
                progress_publisher=progress_events.append,
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(store.downloads[0][0], "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json")
        self.assertEqual(store.uploads[0][2], "application/json")
        self.assertEqual(store.uploaded_payloads[0]["provider"], "mock")
        self.assertEqual(len(store.uploaded_payloads[0]["units"]), 2)
        self.assertEqual(
            event["outputs"],
            {"translated_units": "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json"},
        )
        self.assertEqual([progress["translated_units"] for progress in progress_events], [1, 2])
        self.assertTrue(all(progress["event_type"] == "translate.progress" for progress in progress_events))

    def test_process_hwpx_command_uses_hwpx_translate_stage(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_translate_command(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "hwpx_translate",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                    "source_lang": "en",
                    "target_lang": "ko",
                },
                store=store,
                work_root=Path(temp_dir),
                provider=MockTranslationProvider(),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event["stage"], "hwpx_translate")
        self.assertEqual(store.downloads[0][0], "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json")

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_translate",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "TRANSLATE_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


def _text_units_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "job_id": "job-1",
        "input_type": "docx",
        "source_lang": "en",
        "target_lang": "ko",
        "units": [
            {
                "uid": "unit-000001",
                "text": "Hello world",
                "location": {
                    "type": "docx_run",
                    "path": "word/document.xml",
                    "paragraph_index": 0,
                    "run_index": 0,
                    "text_index": 0,
                },
            },
            {
                "uid": "unit-000002",
                "text": "Translate me",
                "location": {
                    "type": "docx_run",
                    "path": "word/document.xml",
                    "paragraph_index": 0,
                    "run_index": 1,
                    "text_index": 0,
                },
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
