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
sys.path.insert(0, str(ROOT / "services" / "docx-replace-worker"))

from docx_replace_worker.artifacts import (
    DocxReplaceWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_docx_replace_command,
    stage_failed_event,
)
from docx_replace_worker.replacement import replace_docx_text_units


DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{DOCX_NAMESPACE}}}t"


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_docx_texts: list[list[str]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        if object_key.endswith(".docx"):
            _write_minimal_docx(destination, ["Hello world", "Translate me"])
            return
        if object_key.endswith("text_units.json"):
            _write_json(destination, _text_units_payload())
            return
        if object_key.endswith("translated_units.json"):
            _write_json(destination, _translated_units_payload())
            return
        raise AssertionError(f"unexpected download key: {object_key}")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        self.uploaded_docx_texts.append(_read_docx_texts(source))


class DocxReplaceWorkerTests(unittest.TestCase):
    def test_replace_docx_text_units_updates_target_text_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_docx = temp_path / "input.docx"
            text_units = temp_path / "text_units.json"
            translated_units = temp_path / "translated_units.json"
            output_docx = temp_path / "translated.docx"
            _write_minimal_docx(input_docx, ["Hello world", "Translate me"])
            _write_json(text_units, _text_units_payload())
            _write_json(translated_units, _translated_units_payload())

            result = replace_docx_text_units(
                input_docx_path=input_docx,
                text_units_path=text_units,
                translated_units_path=translated_units,
                output_docx_path=output_docx,
            )

            self.assertEqual(result["replaced_units"], 2)
            self.assertEqual(_read_docx_texts(output_docx), ["[ko] Hello world", "[ko] Translate me"])

    def test_worker_command_validates_docx_route_stage_and_input_type(self) -> None:
        command = DocxReplaceWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_replace",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(command.input_type, "pdf")
        with self.assertRaises(ValueError):
            DocxReplaceWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "docx_replace",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            DocxReplaceWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_export",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_pdf_and_docx_routes_and_allow_overrides(self) -> None:
        pdf_command = DocxReplaceWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_replace",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        docx_command = DocxReplaceWorkerCommand.from_message(
            {
                "job_id": "job-2",
                "input_type": "docx",
                "stage": "docx_replace",
                "object_prefix": "2026-01-21/12345678/docxfile",
            }
        )
        override_command = DocxReplaceWorkerCommand.from_message(
            {
                "job_id": "job-3",
                "input_type": "docx",
                "stage": "docx_replace",
                "object_prefix": "2026-01-21/12345678/docxfile",
                "input_docx_key": "custom/input.docx",
                "text_units_object_key": "custom/text_units.json",
                "translated_units_object_key": "custom/translated_units.json",
                "output_object_key": "custom/translated.docx",
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
            artifact_keys_for(docx_command).translated_docx,
            "2026-01-21/12345678/docxfile/04_replace/translated.docx",
        )
        self.assertEqual(artifact_keys_for(override_command).input_docx, "custom/input.docx")
        self.assertEqual(artifact_keys_for(override_command).text_units, "custom/text_units.json")
        self.assertEqual(artifact_keys_for(override_command).translated_units, "custom/translated_units.json")
        self.assertEqual(artifact_keys_for(override_command).translated_docx, "custom/translated.docx")

    def test_process_command_downloads_replaces_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_docx_replace_command(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_replace",
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
                "2026-01-21/12345678/a8f3k2p9/input/original.docx",
                "2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json",
                "2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json",
            ],
        )
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx")
        self.assertEqual(
            store.uploads[0][2],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(store.uploaded_docx_texts[0], ["[ko] Hello world", "[ko] Translate me"])
        self.assertEqual(
            event["outputs"],
            {"translated_docx": "2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx"},
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_replace",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "DOCX_REPLACE_WORKER_FAILED")
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


def _translated_units_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "job_id": "job-1",
        "input_type": "docx",
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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


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


def _read_docx_texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return [node.text or "" for node in root.iter(W_T)]


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    unittest.main()
