"""Artifact key and event flow for docx-replace-worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ft_common.minio_store import ArtifactStore
from docx_replace_worker.replacement import replace_docx_text_units


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class DocxReplaceWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    attempt: int = 1
    input_docx_key: str | None = None
    text_units_object_key: str | None = None
    translated_units_object_key: str | None = None
    output_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "DocxReplaceWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            attempt=int(message.get("attempt", 1)),
            input_docx_key=_optional_str(message.get("input_docx_key")),
            text_units_object_key=_optional_str(message.get("text_units_object_key")),
            translated_units_object_key=_optional_str(message.get("translated_units_object_key")),
            output_object_key=_optional_str(message.get("output_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type not in {"pdf", "docx"}:
            raise ValueError(f"docx-replace-worker requires input_type 'pdf' or 'docx', got {self.input_type!r}")
        if self.stage != "docx_replace":
            raise ValueError(f"docx-replace-worker requires stage='docx_replace', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class DocxReplaceArtifactKeys:
    input_docx: str
    text_units: str
    translated_units: str
    translated_docx: str

    def completed_outputs(self) -> dict[str, str]:
        return {"translated_docx": self.translated_docx}


def artifact_keys_for(command: DocxReplaceWorkerCommand) -> DocxReplaceArtifactKeys:
    prefix = command.object_prefix
    if command.input_docx_key:
        input_docx = command.input_docx_key
    elif command.input_type == "pdf":
        input_docx = f"{prefix}/01_pdf2docx/converted.docx"
    else:
        input_docx = f"{prefix}/input/original.docx"
    return DocxReplaceArtifactKeys(
        input_docx=input_docx,
        text_units=command.text_units_object_key or f"{prefix}/02_extract/text_units.json",
        translated_units=command.translated_units_object_key or f"{prefix}/03_translate/translated_units.json",
        translated_docx=command.output_object_key or f"{prefix}/04_replace/translated.docx",
    )


def process_docx_replace_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
) -> dict[str, object]:
    command = DocxReplaceWorkerCommand.from_message(message)
    keys = artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_docx_path = work_dir / "input.docx"
    text_units_path = work_dir / "text_units.json"
    translated_units_path = work_dir / "translated_units.json"
    output_docx_path = work_dir / "translated.docx"

    store.download_file(keys.input_docx, input_docx_path)
    store.download_file(keys.text_units, text_units_path)
    store.download_file(keys.translated_units, translated_units_path)
    replace_docx_text_units(
        input_docx_path=input_docx_path,
        text_units_path=text_units_path,
        translated_units_path=translated_units_path,
        output_docx_path=output_docx_path,
    )
    store.upload_file(keys.translated_docx, output_docx_path, DOCX_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: DocxReplaceWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
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
    stage = str(message.get("stage", "docx_replace"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "DOCX_REPLACE_WORKER_FAILED",
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

