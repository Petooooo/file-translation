from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "docx-extract-worker"))

from docx_extract_worker.artifacts import (
    DocxExtractWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_docx_extract_command,
    stage_failed_event,
)
from docx_extract_worker.extraction import extract_text_units_from_docx


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_payloads: list[dict[str, object]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        _write_minimal_docx(destination, ["Hello world", "Translate me"])

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        self.uploaded_payloads.append(json.loads(source.read_text(encoding="utf-8")))


class DocxExtractWorkerTests(unittest.TestCase):
    def test_extract_text_units_from_docx_reads_document_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "input.docx"
            _write_minimal_docx(docx_path, ["Hello world", "   ", "Second unit"])

            payload = extract_text_units_from_docx(
                docx_path,
                job_id="job-1",
                input_type="docx",
                source_lang="en",
                target_lang="ko",
            )

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["job_id"], "job-1")
        self.assertEqual(payload["input_type"], "docx")
        self.assertEqual(payload["source_lang"], "en")
        self.assertEqual(payload["target_lang"], "ko")
        self.assertEqual([unit["text"] for unit in payload["units"]], ["Hello world", "Second unit"])
        first_location = payload["units"][0]["location"]
        self.assertEqual(first_location["type"], "docx_run")
        self.assertEqual(first_location["path"], "word/document.xml")
        self.assertEqual(first_location["paragraph_index"], 0)
        self.assertEqual(first_location["run_index"], 0)

    def test_worker_command_validates_stage_and_input_type(self) -> None:
        command = DocxExtractWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_extract",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "source_lang": "en",
                "target_lang": "ko",
            }
        )

        self.assertEqual(command.input_type, "pdf")
        with self.assertRaises(ValueError):
            DocxExtractWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "docx_extract",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            DocxExtractWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_translate",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_pdf_and_docx_routes(self) -> None:
        pdf_command = DocxExtractWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_extract",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        docx_command = DocxExtractWorkerCommand.from_message(
            {
                "job_id": "job-2",
                "input_type": "docx",
                "stage": "docx_extract",
                "object_prefix": "2026-01-21/12345678/docxfile",
            }
        )

        self.assertEqual(
            artifact_keys_for(pdf_command).input_docx,
            "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx",
        )
        self.assertEqual(
            artifact_keys_for(docx_command).input_docx,
            "2026-01-21/12345678/docxfile/input/original.docx",
        )
        self.assertEqual(
            artifact_keys_for(docx_command).text_units,
            "2026-01-21/12345678/docxfile/02_extract/text_units.json",
        )

    def test_input_object_key_override_is_used_when_present(self) -> None:
        command = DocxExtractWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_extract",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "input_object_key": "custom/input.docx",
            }
        )

        self.assertEqual(artifact_keys_for(command).input_docx, "custom/input.docx")

    def test_process_command_downloads_extracts_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_docx_extract_command(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_extract",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                    "source_lang": "en",
                    "target_lang": "ko",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(store.downloads[0][0], "2026-01-21/12345678/a8f3k2p9/input/original.docx")
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json")
        self.assertEqual(store.uploads[0][2], "application/json")
        self.assertEqual(len(store.uploaded_payloads[0]["units"]), 2)
        self.assertEqual(
            event["outputs"],
            {"text_units": "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json"},
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_extract",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "DOCX_EXTRACT_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


def _write_minimal_docx(path: Path, texts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    runs = "".join(f"<w:r><w:t>{_xml_escape(text)}</w:t></w:r>" for text in texts)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p>{runs}</w:p></w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    unittest.main()
