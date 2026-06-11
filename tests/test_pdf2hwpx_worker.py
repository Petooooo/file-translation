from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "pdf2hwpx-worker"))

from pdf2hwpx_worker.artifacts import (
    Pdf2HwpxWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_pdf2hwpx_command,
    stage_failed_event,
)
from pdf2hwpx_worker.placeholder import generate_placeholder_hwpx, read_placeholder_metadata


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_metadata: list[dict[str, object]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        if object_key.endswith(".docx"):
            _write_minimal_docx(destination)
            return
        raise AssertionError(f"unexpected download key: {object_key}")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        self.uploaded_metadata.append(read_placeholder_metadata(source))


class Pdf2HwpxWorkerTests(unittest.TestCase):
    def test_generate_placeholder_hwpx_writes_zip_metadata_and_source_docx(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            marker_docx = temp_path / "marker.docx"
            output_hwpx = temp_path / "final.hwpx"
            _write_minimal_docx(marker_docx)

            result = generate_placeholder_hwpx(
                marker_docx_path=marker_docx,
                output_hwpx_path=output_hwpx,
                job_id="job-1",
                input_type="docx",
                object_prefix="2026-01-21/12345678/a8f3k2p9",
            )

            self.assertEqual(result.output_hwpx, str(output_hwpx))
            self.assertGreater(result.source_docx_size, 0)
            with zipfile.ZipFile(output_hwpx, "r") as archive:
                self.assertEqual(set(archive.namelist()), {"mimetype", "placeholder.json", "source/marker.docx"})
                self.assertEqual(archive.read("source/marker.docx"), marker_docx.read_bytes())
            metadata = read_placeholder_metadata(output_hwpx)
            self.assertEqual(metadata["placeholder"], True)
            self.assertEqual(metadata["stage"], "pdf2hwpx")
            self.assertEqual(metadata["job_id"], "job-1")
            self.assertEqual(metadata["input_type"], "docx")
            self.assertEqual(metadata["object_prefix"], "2026-01-21/12345678/a8f3k2p9")

    def test_worker_command_validates_docx_route_stage_and_input_type(self) -> None:
        command = Pdf2HwpxWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "pdf2hwpx",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(command.input_type, "pdf")
        with self.assertRaises(ValueError):
            Pdf2HwpxWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "pdf2hwpx",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )
        with self.assertRaises(ValueError):
            Pdf2HwpxWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "email_send",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_contract_and_allow_overrides(self) -> None:
        command = Pdf2HwpxWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "pdf2hwpx",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )
        override_command = Pdf2HwpxWorkerCommand.from_message(
            {
                "job_id": "job-2",
                "input_type": "docx",
                "stage": "pdf2hwpx",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                "input_object_key": "custom/marker.docx",
                "output_object_key": "custom/final.hwpx",
            }
        )

        self.assertEqual(
            artifact_keys_for(command).marker_docx,
            "2026-01-21/12345678/a8f3k2p9/05_export/marker.docx",
        )
        self.assertEqual(
            artifact_keys_for(command).final_hwpx,
            "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx",
        )
        self.assertEqual(artifact_keys_for(override_command).marker_docx, "custom/marker.docx")
        self.assertEqual(artifact_keys_for(override_command).final_hwpx, "custom/final.hwpx")

    def test_process_command_downloads_generates_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_pdf2hwpx_command(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "pdf2hwpx",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(
            [download[0] for download in store.downloads],
            ["2026-01-21/12345678/a8f3k2p9/05_export/marker.docx"],
        )
        self.assertEqual(store.uploads[0][0], "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx")
        self.assertEqual(store.uploads[0][2], "application/octet-stream")
        self.assertEqual(store.uploaded_metadata[0]["stage"], "pdf2hwpx")
        self.assertEqual(store.uploaded_metadata[0]["placeholder"], True)
        self.assertEqual(
            event["outputs"],
            {"final_hwpx": "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx"},
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "docx",
                "stage": "pdf2hwpx",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "PDF2HWPX_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


def _write_minimal_docx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>[ko]¡Hello¡world</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
