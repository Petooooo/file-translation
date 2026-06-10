from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "pdf2docx-worker"))

from pdf2docx_worker.conversion import (
    Pdf2DocxConversionRequest,
    build_static_anchored_command,
    default_report_paths,
    run_static_anchored_conversion,
)


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


if __name__ == "__main__":
    unittest.main()
