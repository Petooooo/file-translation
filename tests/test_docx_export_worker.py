from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "libreoffice-worker"))

from libreoffice_worker.artifacts import (
    DocxExportWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_docx_export_command,
    stage_failed_event,
)
from libreoffice_worker.export import export_docx_artifacts


DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{DOCX_NAMESPACE}}}t"


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_docx_texts: list[list[str]] = []
        self.uploaded_pdf_headers: list[bytes] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        if object_key.endswith(".docx"):
            _write_minimal_docx(destination, ["[ko] Hello world", "[ko] Translate me"])
            return
        raise AssertionError(f"unexpected download key: {object_key}")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        if object_key.endswith(".docx"):
            self.uploaded_docx_texts.append(_read_docx_texts(source))
        if object_key.endswith(".pdf"):
            self.uploaded_pdf_headers.append(source.read_bytes()[:8])


class DocxExportWorkerTests(unittest.TestCase):
    def test_export_docx_artifacts_copies_docx_and_writes_placeholder_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_docx = temp_path / "translated.docx"
            final_docx = temp_path / "final.docx"
            final_pdf = temp_path / "final.pdf"
            _write_minimal_docx(input_docx, ["[ko] Hello world"])

            result = export_docx_artifacts(
                input_docx_path=input_docx,
                final_docx_path=final_docx,
                final_pdf_path=final_pdf,
            )

            self.assertEqual(result["pdf_mode"], "placeholder")
            self.assertEqual(_read_docx_texts(final_docx), ["[ko] Hello world"])
            self.assertTrue(final_pdf.read_bytes().startswith(b"%PDF-1.4"))

    def test_worker_command_validates_docx_route_stage_and_input_type(self) -> None:
        command = DocxExportWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_export",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(command.input_type, "pdf")
        with self.assertRaises(ValueError):
            DocxExportWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "docx_export",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            DocxExportWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_marker",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_contract_and_allow_overrides(self) -> None:
        command = DocxExportWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_export",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        override_command = DocxExportWorkerCommand.from_message(
            {
                "job_id": "job-2",
                "input_type": "docx",
                "stage": "docx_export",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "input_object_key": "custom/translated.docx",
                "final_docx_object_key": "custom/final.docx",
                "final_pdf_object_key": "custom/final.pdf",
            }
        )

        self.assertEqual(
            artifact_keys_for(command).translated_docx,
            "2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx",
        )
        self.assertEqual(
            artifact_keys_for(command).final_docx,
            "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
        )
        self.assertEqual(
            artifact_keys_for(command).final_pdf,
            "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
        )
        self.assertEqual(artifact_keys_for(override_command).translated_docx, "custom/translated.docx")
        self.assertEqual(artifact_keys_for(override_command).final_docx, "custom/final.docx")
        self.assertEqual(artifact_keys_for(override_command).final_pdf, "custom/final.pdf")

    def test_process_command_downloads_exports_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_docx_export_command(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_export",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(
            [download[0] for download in store.downloads],
            ["2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx"],
        )
        self.assertEqual(
            [upload[0] for upload in store.uploads],
            [
                "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
                "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
            ],
        )
        self.assertEqual(
            store.uploads[0][2],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(store.uploads[1][2], "application/pdf")
        self.assertEqual(store.uploaded_docx_texts[0], ["[ko] Hello world", "[ko] Translate me"])
        self.assertEqual(store.uploaded_pdf_headers[0], b"%PDF-1.4")
        self.assertEqual(
            event["outputs"],
            {
                "final_docx": "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
                "final_pdf": "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
            },
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_export",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "DOCX_EXPORT_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


def _write_minimal_docx(path: Path, texts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    runs = "".join(f"<w:r><w:t>{text}</w:t></w:r>" for text in texts)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p>{runs}</w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def _read_docx_texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return [node.text or "" for node in root.iter(W_T)]
