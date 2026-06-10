from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "pdf2docx-worker"))

from pdf2docx_worker.artifacts import (
    Pdf2DocxWorkerCommand,
    artifact_keys_for,
    event_queue_key,
    process_pdf2docx_command,
    stage_failed_event,
)
from pdf2docx_worker.conversion import (
    Pdf2DocxConversionRequest,
    build_static_anchored_command,
    default_report_paths,
    run_static_anchored_conversion,
)


class FakeArtifactStore:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.uploads: list[tuple[str, Path, str | None]] = []

    def download_file(self, object_key: str, destination: Path) -> None:
        self.downloads.append((object_key, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"%PDF-1.4\n")

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        self.uploads.append((object_key, source, content_type))


class Pdf2DocxWorkerTests(unittest.TestCase):
    def test_build_static_anchored_command_uses_required_cli(self) -> None:
        request = Pdf2DocxConversionRequest(
            input_path=Path("/work/input.pdf"),
            output_path=Path("/work/output.docx"),
            overwrite=True,
        )

        self.assertEqual(
            build_static_anchored_command(request, python_executable="python"),
            [
                "python",
                "-m",
                "pdf2docx.static_anchored.cli",
                "--input",
                "/work/input.pdf",
                "--output",
                "/work/output.docx",
                "--overwrite",
            ],
        )

    def test_build_static_anchored_command_adds_reports(self) -> None:
        request = Pdf2DocxConversionRequest(
            input_path=Path("/work/input.pdf"),
            output_path=Path("/work/output.docx"),
            report_json_path=Path("/work/output.report.json"),
            report_markdown_path=Path("/work/output.report.md"),
            overwrite=True,
        )

        command = build_static_anchored_command(request, python_executable="python")

        self.assertIn("--report", command)
        self.assertIn("/work/output.report.json", command)
        self.assertIn("--markdown-report", command)
        self.assertIn("/work/output.report.md", command)

    def test_default_report_paths_follow_output_stem(self) -> None:
        report_json, report_md = default_report_paths(Path("/work/out/sample.static.docx"))

        self.assertEqual(report_json, Path("/work/out/sample.static.report.json"))
        self.assertEqual(report_md, Path("/work/out/sample.static.report.md"))

    def test_run_conversion_validates_pdf_input_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.txt"
            input_path.write_text("not a pdf", encoding="utf-8")

            with self.assertRaises(ValueError):
                run_static_anchored_conversion(
                    Pdf2DocxConversionRequest(
                        input_path=input_path,
                        output_path=Path(temp_dir) / "output.docx",
                    )
                )

    def test_run_conversion_returns_outputs_from_fake_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.pdf"
            output_path = Path(temp_dir) / "output.docx"
            report_json = Path(temp_dir) / "output.report.json"
            report_md = Path(temp_dir) / "output.report.md"
            input_path.write_bytes(b"%PDF-1.4\n")

            def fake_runner(command, check, capture_output, text):
                self.assertFalse(check)
                self.assertTrue(capture_output)
                self.assertTrue(text)
                output_path.write_bytes(b"docx")
                report_json.write_text("{}", encoding="utf-8")
                report_md.write_text("# report\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            result = run_static_anchored_conversion(
                Pdf2DocxConversionRequest(
                    input_path=input_path,
                    output_path=output_path,
                    report_json_path=report_json,
                    report_markdown_path=report_md,
                ),
                runner=fake_runner,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.outputs(),
                {
                    "converted_docx": str(output_path),
                    "pdf2docx_report_json": str(report_json),
                    "pdf2docx_report_md": str(report_md),
                },
            )

    def test_worker_command_validates_stage_and_type(self) -> None:
        command = Pdf2DocxWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "pdf2docx",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        self.assertEqual(command.job_id, "job-1")
        with self.assertRaises(ValueError):
            Pdf2DocxWorkerCommand.from_message(
                {
                    "job_id": "job-1",
                    "input_type": "docx",
                    "stage": "pdf2docx",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                }
            )

    def test_artifact_keys_follow_minio_contract(self) -> None:
        command = Pdf2DocxWorkerCommand.from_message(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "pdf2docx",
                "object_prefix": "2026-01-21/12345678/a8f3k2p9",
            }
        )

        keys = artifact_keys_for(command, reports_enabled=True)

        self.assertEqual(keys.input_pdf, "2026-01-21/12345678/a8f3k2p9/input/original.pdf")
        self.assertEqual(keys.converted_docx, "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx")
        self.assertEqual(keys.report_json, "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json")
        self.assertEqual(keys.report_markdown, "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md")

    def test_process_command_downloads_converts_uploads_and_returns_completed_event(self) -> None:
        store = FakeArtifactStore()

        def fake_converter(request: Pdf2DocxConversionRequest):
            request.output_path.write_bytes(b"docx")
            assert request.report_json_path is not None
            assert request.report_markdown_path is not None
            request.report_json_path.write_text("{}", encoding="utf-8")
            request.report_markdown_path.write_text("# report\n", encoding="utf-8")
            return object()

        with tempfile.TemporaryDirectory() as temp_dir:
            event = process_pdf2docx_command(
                {
                    "job_id": "job-1",
                    "input_type": "pdf",
                    "stage": "pdf2docx",
                    "object_prefix": "2026-01-21/12345678/a8f3k2p9",
                },
                store=store,
                work_root=Path(temp_dir),
                reports_enabled=True,
                converter=fake_converter,
            )

        self.assertEqual(event["event_type"], "stage.completed")
        self.assertEqual(event_queue_key(event), "stage_completed")
        self.assertEqual(store.downloads[0][0], "2026-01-21/12345678/a8f3k2p9/input/original.pdf")
        self.assertEqual(
            [upload[0] for upload in store.uploads],
            [
                "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx",
                "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json",
                "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md",
            ],
        )
        self.assertEqual(
            event["outputs"],
            {
                "converted_docx": "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx",
                "pdf2docx_report_json": "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json",
                "pdf2docx_report_md": "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md",
            },
        )

    def test_stage_failed_event_uses_worker_failure_contract(self) -> None:
        event = stage_failed_event(
            {
                "job_id": "job-1",
                "input_type": "pdf",
                "stage": "pdf2docx",
            },
            RuntimeError("boom"),
        )

        self.assertEqual(event["event_type"], "stage.failed")
        self.assertEqual(event_queue_key(event), "stage_failed")
        self.assertEqual(event["error_code"], "PDF2DOCX_WORKER_FAILED")
        self.assertEqual(event["error_message"], "boom")


if __name__ == "__main__":
    unittest.main()
