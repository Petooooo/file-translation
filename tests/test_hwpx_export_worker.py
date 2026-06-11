from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "libreoffice-worker"))

from libreoffice_worker.hwpx_artifacts import (
    HwpxExportWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_hwpx_export_command,
    stage_failed_event,
)
from libreoffice_worker.hwpx_export import export_hwpx_artifacts


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []
        self.uploaded_pdf_headers: list[bytes] = []
        self.uploaded_docx_entries: list[list[str]] = []
        self.uploaded_hwpx_entries: list[list[str]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        if object_key.endswith(".hwpx"):
            _write_sample_hwpx(destination)
            return
        raise AssertionError(f"unexpected download key: {object_key}")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))
        if object_key.endswith(".pdf"):
            self.uploaded_pdf_headers.append(source.read_bytes()[:8])
        if object_key.endswith(".docx"):
            with zipfile.ZipFile(source, "r") as archive:
                self.uploaded_docx_entries.append(sorted(archive.namelist()))
        if object_key.endswith(".hwpx"):
            with zipfile.ZipFile(source, "r") as archive:
                self.uploaded_hwpx_entries.append(sorted(archive.namelist()))


class HwpxExportWorkerTests(unittest.TestCase):
    def test_export_hwpx_artifacts_writes_placeholder_docx_pdf_and_copies_hwpx(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_hwpx = temp_path / "translated.hwpx"
            final_hwpx = temp_path / "final.hwpx"
            final_docx = temp_path / "final.docx"
            final_pdf = temp_path / "final.pdf"
            _write_sample_hwpx(input_hwpx)

            result = export_hwpx_artifacts(
                input_hwpx_path=input_hwpx,
                final_hwpx_path=final_hwpx,
                final_docx_path=final_docx,
                final_pdf_path=final_pdf,
            )

            self.assertFalse(result["h2o_export_enabled"])
            self.assertTrue(final_pdf.read_bytes().startswith(b"%PDF-1.4"))
            self.assertEqual(final_hwpx.read_bytes(), input_hwpx.read_bytes())
            with zipfile.ZipFile(final_docx, "r") as archive:
                self.assertIn("word/document.xml", archive.namelist())

    def test_real_h2o_export_path_is_explicitly_unimplemented(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_hwpx = temp_path / "translated.hwpx"
            _write_sample_hwpx(input_hwpx)

            with self.assertRaises(RuntimeError):
                export_hwpx_artifacts(
                    input_hwpx_path=input_hwpx,
                    final_hwpx_path=temp_path / "final.hwpx",
                    final_docx_path=temp_path / "final.docx",
                    final_pdf_path=temp_path / "final.pdf",
                    h2o_export_enabled=True,
                )

    def test_worker_command_validates_hwpx_route_stage_and_keys(self) -> None:
        command = HwpxExportWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "hwpx",
                "stage": "hwpx_export",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(artifact_keys_for(command).translated_hwpx, "2026-01-21/12345678/a8f3k2p9/04_replace/translated.hwpx")
        self.assertEqual(artifact_keys_for(command).final_docx, "2026-01-21/12345678/a8f3k2p9/05_export/final.docx")
        self.assertEqual(artifact_keys_for(command).final_pdf, "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf")
        self.assertEqual(artifact_keys_for(command).final_hwpx, "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx")
        with self.assertRaises(ValueError):
            HwpxExportWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "hwpx_export",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_process_command_downloads_exports_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_hwpx_export_command(
                {
                    "job_id": "job-1",
                    "input_type": "hwpx",
                    "stage": "hwpx_export",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                },
                store=store,
                work_root=Path(temp_dir),
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(store.downloads[0][0], "2026-01-21/12345678/a8f3k2p9/04_replace/translated.hwpx")
        self.assertEqual(
            [upload[0] for upload in store.uploads],
            [
                "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
                "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
                "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx",
            ],
        )
        self.assertEqual(store.uploads[0][2], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertEqual(store.uploads[1][2], "application/pdf")
        self.assertEqual(store.uploads[2][2], "application/octet-stream")
        self.assertEqual(store.uploaded_pdf_headers[0], b"%PDF-1.4")
        self.assertIn("word/document.xml", store.uploaded_docx_entries[0])
        self.assertIn("Contents/section0.xml", store.uploaded_hwpx_entries[0])
        self.assertEqual(
            event["outputs"],
            {
                "final_docx": "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
                "final_pdf": "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
                "final_hwpx": "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx",
            },
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "hwpx",
                "stage": "hwpx_export",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "HWPX_EXPORT_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


def _write_sample_hwpx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Contents/section0.xml", "<section><p><t>[ko] Hello world</t></p></section>")


if __name__ == "__main__":
    unittest.main()
