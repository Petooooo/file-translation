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

from libreoffice_worker.marker import mark_docx_spaces
from libreoffice_worker.marker_artifacts import (
    DocxMarkerWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_docx_marker_command,
    stage_failed_event,
)


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
            _write_minimal_docx(destination, ["[ko] Hello world", "NoSpace", "A B C"])
            return
        raise AssertionError(f"unexpected download key: {object_key}")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        self.uploaded_docx_texts.append(_read_docx_texts(source))


class DocxMarkerWorkerTests(unittest.TestCase):
    def test_mark_docx_spaces_replaces_spaces_in_word_xml_text_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_docx = temp_path / "final.docx"
            marker_docx = temp_path / "marker.docx"
            _write_minimal_docx(input_docx, ["Hello world", "NoSpace", "A B C"])

            result = mark_docx_spaces(input_docx_path=input_docx, marker_docx_path=marker_docx)

            self.assertEqual(result.marked_text_nodes, 2)
            self.assertEqual(result.replaced_spaces, 3)
            self.assertEqual(_read_docx_texts(marker_docx), ["Hello¡world", "NoSpace", "A¡B¡C"])

    def test_worker_command_validates_docx_route_stage_and_input_type(self) -> None:
        command = DocxMarkerWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "docx_marker",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(command.input_type, "pdf")
        with self.assertRaises(ValueError):
            DocxMarkerWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "docx_marker",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            DocxMarkerWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "pdf2hwpx",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_contract_and_allow_overrides(self) -> None:
        command = DocxMarkerWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_marker",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        override_command = DocxMarkerWorkerCommand.from_message(
            {
                "job_id": "job-2",
                "input_type": "docx",
                "stage": "docx_marker",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "input_object_key": "custom/final.docx",
                "marker_docx_object_key": "custom/marker.docx",
            }
        )

        self.assertEqual(
            artifact_keys_for(command).final_docx,
            "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
        )
        self.assertEqual(
            artifact_keys_for(command).marker_docx,
            "2026-01-21/12345678/a8f3k2p9/05_export/marker.docx",
        )
        self.assertEqual(artifact_keys_for(override_command).final_docx, "custom/final.docx")
        self.assertEqual(artifact_keys_for(override_command).marker_docx, "custom/marker.docx")

    def test_process_command_downloads_marks_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_docx_marker_command(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "docx_marker",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(
            [download[0] for download in store.downloads],
            ["2026-01-21/12345678/a8f3k2p9/05_export/final.docx"],
        )
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/05_export/marker.docx")
        self.assertEqual(
            store.uploads[0][2],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(store.uploaded_docx_texts[0], ["[ko]¡Hello¡world", "NoSpace", "A¡B¡C"])
        self.assertEqual(
            event["outputs"],
            {"marker_docx": "2026-01-21/12345678/a8f3k2p9/05_export/marker.docx"},
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "docx_marker",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "DOCX_MARKER_WORKER_FAILED")
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
