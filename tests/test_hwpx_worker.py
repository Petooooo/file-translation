from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "hwpx-worker"))

from hwpx_worker.artifacts import (
    HwpxExtractWorkerCommand,
    HwpxReplaceWorkerCommand,
    event_queue_key,
    extract_artifact_keys_for,
    process_hwpx_extract_command,
    process_hwpx_replace_command,
    replace_artifact_keys_for,
    stage_failed_event,
)
from hwpx_worker.hwpx_xml import create_sample_hwpx, extract_text_units_from_hwpx, replace_hwpx_text_units, write_text_units_json


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_json: list[dict[str, object]] = []
        self.uploaded_hwpx_texts: list[list[str]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        if object_key.endswith("original.hwpx"):
            create_sample_hwpx(destination, ["Hello world", "Translate me"])
            return
        if object_key.endswith("text_units.json"):
            write_text_units_json(_text_units_payload(), destination)
            return
        if object_key.endswith("translated_units.json"):
            destination.write_text(json.dumps(_translated_units_payload()), encoding="utf-8")
            return
        raise AssertionError(f"unexpected download key: {object_key}")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        if object_key.endswith(".json"):
            self.uploaded_json.append(json.loads(source.read_text(encoding="utf-8")))
        if object_key.endswith(".hwpx"):
            self.uploaded_hwpx_texts.append(_read_sample_hwpx_texts(source))


class HwpxWorkerTests(unittest.TestCase):
    def test_local_stub_extracts_and_replaces_text_units(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_hwpx = temp_path / "input.hwpx"
            text_units = temp_path / "text_units.json"
            translated_units = temp_path / "translated_units.json"
            output_hwpx = temp_path / "translated.hwpx"
            create_sample_hwpx(input_hwpx, ["Hello world", "Translate me"])

            payload = extract_text_units_from_hwpx(
                input_hwpx,
                job_id="job-1",
                input_type="hwpx",
                source_lang="en",
                target_lang="ko",
            )
            write_text_units_json(payload, text_units)
            translated_units.write_text(json.dumps(_translated_units_payload()), encoding="utf-8")

            result = replace_hwpx_text_units(
                input_hwpx_path=input_hwpx,
                text_units_path=text_units,
                translated_units_path=translated_units,
                output_hwpx_path=output_hwpx,
            )
            replaced_texts = _read_sample_hwpx_texts(output_hwpx)

        self.assertEqual([unit["text"] for unit in payload["units"]], ["Hello world", "Translate me"])
        self.assertEqual(result["replaced_units"], 2)
        self.assertEqual(replaced_texts, ["[ko] Hello world", "[ko] Translate me"])

    def test_worker_commands_validate_hwpx_stages_and_keys(self) -> None:
        extract_command = HwpxExtractWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "hwpx",
                "stage": "hwpx_extract",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        replace_command = HwpxReplaceWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "hwpx",
                "stage": "hwpx_replace",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(extract_artifact_keys_for(extract_command).input_hwpx, "2026-01-21/12345678/a8f3k2p9/input/original.hwpx")
        self.assertEqual(extract_artifact_keys_for(extract_command).text_units, "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(replace_artifact_keys_for(replace_command).translated_hwpx, "2026-01-21/12345678/a8f3k2p9/04_replace/translated.hwpx")
        with self.assertRaises(ValueError):
            HwpxExtractWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "hwpx_extract",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            HwpxReplaceWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "docx_replace",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_process_extract_downloads_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_hwpx_extract_command(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "hwpx_extract",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                    "source_lang": "en",
                    "target_lang": "ko",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(store.downloads[0][0], "2026-01-21/12345678/a8f3k2p9/input/original.hwpx")
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(store.uploads[0][2], "application/json")
        self.assertEqual(store.uploaded_json[0]["input_type"], "hwpx")
        self.assertEqual(event["outputs"], {"text_units": "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json"})

    def test_process_replace_downloads_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_hwpx_replace_command(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "hwpx_replace",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(
            [download[0] for download in store.downloads],
            [
                "2026-01-21/12345678/a8f3k2p9/input/original.hwpx",
                "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json",
                "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json",
            ],
        )
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/04_replace/translated.hwpx")
        self.assertEqual(store.uploaded_hwpx_texts[0], ["[ko] Hello world", "[ko] Translate me"])
        self.assertEqual(event["outputs"], {"translated_hwpx": "2026-01-21/12345678/a8f3k2p9/04_replace/translated.hwpx"})

    def test_stage_failed_event_uses_stage_specific_error_code(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "hwpx",
                "stage": "hwpx_replace",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "HWPX_REPLACE_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


def _text_units_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "job_id": "job-1",
        "input_type": "hwpx",
        "source_lang": "en",
        "target_lang": "ko",
        "units": [
            {
                "uid": "unit-000001",
                "text": "Hello world",
                "location": {
                    "type": "hwpx_xml_text",
                    "path": "Contents/section0.xml",
                    "element_index": 0,
                },
            },
            {
                "uid": "unit-000002",
                "text": "Translate me",
                "location": {
                    "type": "hwpx_xml_text",
                    "path": "Contents/section0.xml",
                    "element_index": 1,
                },
            },
        ],
    }


def _translated_units_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "job_id": "job-1",
        "input_type": "hwpx",
        "source_lang": "en",
        "target_lang": "ko",
        "provider": "mock",
        "units": [
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
    }


def _read_sample_hwpx_texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        root = ET.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter("t")]


if __name__ == "__main__":
    unittest.main()
