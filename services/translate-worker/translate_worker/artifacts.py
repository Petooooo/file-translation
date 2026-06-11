"""Artifact key and event flow for translate-worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ft_common.minio_store import ArtifactStore
from translate_worker.provider import TranslationProvider
from translate_worker.translation import (
    read_text_units_json,
    translate_text_units,
    write_translated_units_json,
)


JSON_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class TranslateWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    source_lang: str | None = None
    target_lang: str | None = None
    attempt: int = 1
    input_object_key: str | None = None
    output_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "TranslateWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            source_lang=_optional_str(message.get("source_lang")),
            target_lang=_optional_str(message.get("target_lang")),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
            output_object_key=_optional_str(message.get("output_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type not in {"pdf", "docx"}:
            raise ValueError(f"translate-worker docx route requires input_type 'pdf' or 'docx', got {self.input_type!r}")
        if self.stage != "docx_translate":
            raise ValueError(f"translate-worker requires stage='docx_translate', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class TranslateArtifactKeys:
    text_units: str
    translated_units: str

    def completed_outputs(self) -> dict[str, str]:
        return {"translated_units": self.translated_units}


ProgressPublisher = Callable[[dict[str, object]], None]


def artifact_keys_for(command: TranslateWorkerCommand) -> TranslateArtifactKeys:
    prefix = command.object_prefix
    return TranslateArtifactKeys(
        text_units=command.input_object_key or f"{prefix}/02_extract/text_units.json",
        translated_units=command.output_object_key or f"{prefix}/03_translate/translated_units.json",
    )


def process_translate_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
    provider: TranslationProvider,
    progress_publisher: ProgressPublisher | None = None,
) -> dict[str, object]:
    command = TranslateWorkerCommand.from_message(message)
    keys = artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_path = work_dir / "text_units.json"
    output_path = work_dir / "translated_units.json"

    store.download_file(keys.text_units, input_path)
    text_units_payload = read_text_units_json(input_path)

    def publish_progress(total_units: int, translated_units: int, failed_units: int) -> None:
        if progress_publisher is not None:
            progress_publisher(
                progress_event(
                    command,
                    total_units=total_units,
                    translated_units=translated_units,
                    failed_units=failed_units,
                )
            )

    translated_payload = translate_text_units(
        text_units_payload,
        provider=provider,
        source_lang=command.source_lang,
        target_lang=command.target_lang,
        progress_callback=publish_progress,
    )
    write_translated_units_json(translated_payload, output_path)
    store.upload_file(keys.translated_units, output_path, JSON_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: TranslateWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
    return {
        "event_type": "stage.completed",
        "job_id": command.job_id,
        "input_type": command.input_type,
        "stage": command.stage,
        "outputs": outputs,
    }


def progress_event(
    command: TranslateWorkerCommand,
    *,
    total_units: int,
    translated_units: int,
    failed_units: int,
) -> dict[str, object]:
    return {
        "event_type": "translate.progress",
        "job_id": command.job_id,
        "input_type": command.input_type,
        "stage": command.stage,
        "total_units": total_units,
        "translated_units": translated_units,
        "failed_units": failed_units,
    }


def stage_failed_event(message: dict[str, object], error: Exception) -> dict[str, object]:
    job_id = str(message.get("job_id", "unknown"))
    input_type = str(message.get("input_type", "docx"))
    stage = str(message.get("stage", "docx_translate"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "TRANSLATE_WORKER_FAILED",
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
