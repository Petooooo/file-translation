"""Static anchored pdf2docx conversion command wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence


DEFAULT_CLI_MODULE = "pdf2docx.static_anchored.cli"


@dataclass(frozen=True)
class Pdf2DocxConversionRequest:
    input_path: Path
    output_path: Path
    overwrite: bool = True
    report_json_path: Path | None = None
    report_markdown_path: Path | None = None
    password: str | None = None
    cli_module: str = DEFAULT_CLI_MODULE


@dataclass(frozen=True)
class Pdf2DocxConversionResult:
    input_path: Path
    output_path: Path
    report_json_path: Path | None
    report_markdown_path: Path | None
    returncode: int
    stdout: str
    stderr: str

    def outputs(self) -> dict[str, str]:
        outputs = {"converted_docx": str(self.output_path)}
        if self.report_json_path is not None:
            outputs["pdf2docx_report_json"] = str(self.report_json_path)
        if self.report_markdown_path is not None:
            outputs["pdf2docx_report_md"] = str(self.report_markdown_path)
        return outputs


class Pdf2DocxConversionError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int, stdout: str, stderr: str) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"pdf2docx conversion failed with returncode={returncode}")


Runner = Callable[..., subprocess.CompletedProcess[str]]


def default_report_paths(output_path: Path) -> tuple[Path, Path]:
    return output_path.with_suffix(".report.json"), output_path.with_suffix(".report.md")


def build_static_anchored_command(
    request: Pdf2DocxConversionRequest,
    python_executable: str | None = None,
) -> list[str]:
    command = [
        python_executable or sys.executable,
        "-m",
        request.cli_module,
        "--input",
        str(request.input_path),
        "--output",
        str(request.output_path),
    ]
    if request.report_json_path is not None:
        command.extend(["--report", str(request.report_json_path)])
    if request.report_markdown_path is not None:
        command.extend(["--markdown-report", str(request.report_markdown_path)])
    if request.password:
        command.extend(["--password", request.password])
    if request.overwrite:
        command.append("--overwrite")
    return command


def run_static_anchored_conversion(
    request: Pdf2DocxConversionRequest,
    runner: Runner | None = None,
) -> Pdf2DocxConversionResult:
    _validate_request(request)
    command = build_static_anchored_command(request)
    completed = (runner or subprocess.run)(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise Pdf2DocxConversionError(command, completed.returncode, completed.stdout, completed.stderr)
    return Pdf2DocxConversionResult(
        input_path=request.input_path,
        output_path=request.output_path,
        report_json_path=request.report_json_path,
        report_markdown_path=request.report_markdown_path,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _validate_request(request: Pdf2DocxConversionRequest) -> None:
    if not request.input_path.exists():
        raise FileNotFoundError(f"input PDF does not exist: {request.input_path}")
    if request.input_path.suffix.lower() != ".pdf":
        raise ValueError(f"input must be a PDF file: {request.input_path}")
    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    if request.report_json_path is not None:
        request.report_json_path.parent.mkdir(parents=True, exist_ok=True)
    if request.report_markdown_path is not None:
        request.report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
