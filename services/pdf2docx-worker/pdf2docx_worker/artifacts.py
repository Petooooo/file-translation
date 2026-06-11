"""Artifact key and event flow for pdf2docx-worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ft_common.minio_store import ArtifactStore
from pdf2docx_worker.conversion import Pdf2DocxConversionRequest, run_static_anchored_conversion


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
JSON_CONTENT_TYPE = "application/json"
MARKDOWN_CONTENT_TYPE = "text/markdown"


@dataclass(frozen=True)
class Pdf2DocxWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    attempt: int = 1
    input_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "Pdf2DocxWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type != "pdf":
            raise ValueError(f"pdf2docx-worker requires input_type='pdf', got {self.input_type!r}")
        if self.stage != "pdf2docx":
            raise ValueError(f"pdf2docx-worker requires stage='pdf2docx', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class Pdf2DocxArtifactKeys:
    input_pdf: str
    converted_docx: str
    report_json: str | None
    report_markdown: str | None

    def completed_outputs(self) -> dict[str, str]:
        outputs = {"converted_docx": self.converted_docx}
        if self.report_json is not None:
            outputs["pdf2docx_report_json"] = self.report_json
        if self.report_markdown is not None:
            outputs["pdf2docx_report_md"] = self.report_markdown
        return outputs


Converter = Callable[[Pdf2DocxConversionRequest], object]


def artifact_keys_for(command: Pdf2DocxWorkerCommand, reports_enabled: bool) -> Pdf2DocxArtifactKeys:
    prefix = command.object_prefix
    return Pdf2DocxArtifactKeys(
        input_pdf=command.input_object_key or f"{prefix}/input/original.pdf",
        converted_docx=f"{prefix}/01_pdf2docx/converted.docx",
        report_json=f"{prefix}/reports/pdf2docx.report.json" if reports_enabled else None,
        report_markdown=f"{prefix}/reports/pdf2docx.report.md" if reports_enabled else None,
    )


def process_pdf2docx_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
    reports_enabled: bool,
    converter: Converter = run_static_anchored_conversion,
) -> dict[str, object]:
    command = Pdf2DocxWorkerCommand.from_message(message)
    keys = artifact_keys_for(command, reports_enabled)
    work_dir = work_root / _safe_segment(command.job_id)
    input_path = work_dir / "input.pdf"
    output_path = work_dir / "converted.docx"
    report_json_path = work_dir / "pdf2docx.report.json" if keys.report_json else None
    report_markdown_path = work_dir / "pdf2docx.report.md" if keys.report_markdown else None

    store.download_file(keys.input_pdf, input_path)
    converter(
        Pdf2DocxConversionRequest(
            input_path=input_path,
            output_path=output_path,
            overwrite=True,
            report_json_path=report_json_path,
            report_markdown_path=report_markdown_path,
        )
    )
    store.upload_file(keys.converted_docx, output_path, DOCX_CONTENT_TYPE)
    if keys.report_json is not None and report_json_path is not None:
        store.upload_file(keys.report_json, report_json_path, JSON_CONTENT_TYPE)
    if keys.report_markdown is not None and report_markdown_path is not None:
        store.upload_file(keys.report_markdown, report_markdown_path, MARKDOWN_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: Pdf2DocxWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
    return {
        "event_type": "stage.completed",
        "job_id": command.job_id,
        "input_type": command.input_type,
        "stage": command.stage,
        "outputs": outputs,
    }


def stage_failed_event(message: dict[str, object], error: Exception) -> dict[str, object]:
    job_id = str(message.get("job_id", "unknown"))
    input_type = str(message.get("input_type", "pdf"))
    stage = str(message.get("stage", "pdf2docx"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "PDF2DOCX_WORKER_FAILED",
        "error_message": str(error),
        "retryable": False,
    }


def event_queue_key(event: dict[str, object]) -> str:
    event_type = str(event.get("event_type", ""))
    if event_type == "stage.completed":
        return "stage_completed"
    if event_type == "stage.failed":
        return "stage_failed"
    return "progress"


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _safe_segment(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "job"
