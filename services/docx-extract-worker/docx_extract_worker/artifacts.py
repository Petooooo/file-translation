"""Artifact key and event flow for docx-extract-worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ft_common.minio_store import ArtifactStore
from docx_extract_worker.extraction import extract_text_units_from_docx, write_text_units_json


JSON_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class DocxExtractWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    source_lang: str = "und"
    target_lang: str = "und"
    attempt: int = 1
    input_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "DocxExtractWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            source_lang=str(message.get("source_lang", "und")),
            target_lang=str(message.get("target_lang", "und")),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type not in {"pdf", "docx"}:
            raise ValueError(f"docx-extract-worker requires input_type 'pdf' or 'docx', got {self.input_type!r}")
        if self.stage != "docx_extract":
            raise ValueError(f"docx-extract-worker requires stage='docx_extract', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class DocxExtractArtifactKeys:
    input_docx: str
    text_units: str

    def completed_outputs(self) -> dict[str, str]:
        return {"text_units": self.text_units}


Extractor = Callable[..., dict[str, object]]


def artifact_keys_for(command: DocxExtractWorkerCommand) -> DocxExtractArtifactKeys:
    prefix = command.object_prefix
    if command.input_object_key:
        input_docx = command.input_object_key
    elif command.input_type == "pdf":
        input_docx = f"{prefix}/01_pdf2docx/converted.docx"
    else:
        input_docx = f"{prefix}/input/original.docx"
    return DocxExtractArtifactKeys(
        input_docx=input_docx,
        text_units=f"{prefix}/02_extract/text_units.json",
    )


def process_docx_extract_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
    extractor: Extractor = extract_text_units_from_docx,
) -> dict[str, object]:
    command = DocxExtractWorkerCommand.from_message(message)
    keys = artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_path = work_dir / "input.docx"
    output_path = work_dir / "text_units.json"

    store.download_file(keys.input_docx, input_path)
    payload = extractor(
        input_path,
        job_id=command.job_id,
        input_type=command.input_type,
        source_lang=command.source_lang,
        target_lang=command.target_lang,
    )
    write_text_units_json(payload, output_path)
    store.upload_file(keys.text_units, output_path, JSON_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: DocxExtractWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
    return {
        "event_type": "stage.completed",
        "job_id": command.job_id,
        "input_type": command.input_type,
        "stage": command.stage,
        "outputs": outputs,
    }


def stage_failed_event(message: dict[str, object], error: Exception) -> dict[str, object]:
    job_id = str(message.get("job_id", "unknown"))
    input_type = str(message.get("input_type", "docx"))
    stage = str(message.get("stage", "docx_extract"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "DOCX_EXTRACT_WORKER_FAILED",
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

