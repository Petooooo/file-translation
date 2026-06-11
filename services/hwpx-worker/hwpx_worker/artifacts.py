"""Artifact key and event flow for the HWPX direct route."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ft_common.minio_store import ArtifactStore
from hwpx_worker.hwpx_xml import (
    extract_text_units_from_hwpx,
    replace_hwpx_text_units,
    write_text_units_json,
)


JSON_CONTENT_TYPE = "application/json"
HWPX_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class HwpxExtractWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    source_lang: str = "und"
    target_lang: str = "und"
    attempt: int = 1
    input_object_key: str | None = None
    output_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "HwpxExtractWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            source_lang=str(message.get("source_lang", "und")),
            target_lang=str(message.get("target_lang", "und")),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
            output_object_key=_optional_str(message.get("output_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type != "hwpx":
            raise ValueError(f"hwpx-worker extract requires input_type 'hwpx', got {self.input_type!r}")
        if self.stage != "hwpx_extract":
            raise ValueError(f"hwpx-worker extract requires stage='hwpx_extract', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class HwpxReplaceWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    attempt: int = 1
    input_hwpx_key: str | None = None
    text_units_object_key: str | None = None
    translated_units_object_key: str | None = None
    output_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "HwpxReplaceWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            attempt=int(message.get("attempt", 1)),
            input_hwpx_key=_optional_str(message.get("input_hwpx_key")),
            text_units_object_key=_optional_str(message.get("text_units_object_key")),
            translated_units_object_key=_optional_str(message.get("translated_units_object_key")),
            output_object_key=_optional_str(message.get("output_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type != "hwpx":
            raise ValueError(f"hwpx-worker replace requires input_type 'hwpx', got {self.input_type!r}")
        if self.stage != "hwpx_replace":
            raise ValueError(f"hwpx-worker replace requires stage='hwpx_replace', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class HwpxExtractArtifactKeys:
    input_hwpx: str
    text_units: str

    def completed_outputs(self) -> dict[str, str]:
        return {"text_units": self.text_units}


@dataclass(frozen=True)
class HwpxReplaceArtifactKeys:
    input_hwpx: str
    text_units: str
    translated_units: str
    translated_hwpx: str

    def completed_outputs(self) -> dict[str, str]:
        return {"translated_hwpx": self.translated_hwpx}


def extract_artifact_keys_for(command: HwpxExtractWorkerCommand) -> HwpxExtractArtifactKeys:
    prefix = command.object_prefix
    return HwpxExtractArtifactKeys(
        input_hwpx=command.input_object_key or f"{prefix}/input/original.hwpx",
        text_units=command.output_object_key or f"{prefix}/02_extract/text_units.json",
    )


def replace_artifact_keys_for(command: HwpxReplaceWorkerCommand) -> HwpxReplaceArtifactKeys:
    prefix = command.object_prefix
    return HwpxReplaceArtifactKeys(
        input_hwpx=command.input_hwpx_key or f"{prefix}/input/original.hwpx",
        text_units=command.text_units_object_key or f"{prefix}/02_extract/text_units.json",
        translated_units=command.translated_units_object_key or f"{prefix}/03_translate/translated_units.json",
        translated_hwpx=command.output_object_key or f"{prefix}/04_replace/translated.hwpx",
    )


def process_hwpx_extract_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
) -> dict[str, object]:
    command = HwpxExtractWorkerCommand.from_message(message)
    keys = extract_artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_path = work_dir / "input.hwpx"
    output_path = work_dir / "text_units.json"

    store.download_file(keys.input_hwpx, input_path)
    payload = extract_text_units_from_hwpx(
        input_path,
        job_id=command.job_id,
        input_type=command.input_type,
        source_lang=command.source_lang,
        target_lang=command.target_lang,
    )
    write_text_units_json(payload, output_path)
    store.upload_file(keys.text_units, output_path, JSON_CONTENT_TYPE)

    return stage_completed_event(command.job_id, command.input_type, command.stage, keys.completed_outputs())


def process_hwpx_replace_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
) -> dict[str, object]:
    command = HwpxReplaceWorkerCommand.from_message(message)
    keys = replace_artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_hwpx_path = work_dir / "input.hwpx"
    text_units_path = work_dir / "text_units.json"
    translated_units_path = work_dir / "translated_units.json"
    output_hwpx_path = work_dir / "translated.hwpx"

    store.download_file(keys.input_hwpx, input_hwpx_path)
    store.download_file(keys.text_units, text_units_path)
    store.download_file(keys.translated_units, translated_units_path)
    replace_hwpx_text_units(
        input_hwpx_path=input_hwpx_path,
        text_units_path=text_units_path,
        translated_units_path=translated_units_path,
        output_hwpx_path=output_hwpx_path,
    )
    store.upload_file(keys.translated_hwpx, output_hwpx_path, HWPX_CONTENT_TYPE)

    return stage_completed_event(command.job_id, command.input_type, command.stage, keys.completed_outputs())


def stage_completed_event(job_id: str, input_type: str, stage: str, outputs: dict[str, str]) -> dict[str, object]:
    return {
        "event_type": "stage.completed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "outputs": outputs,
    }


def stage_failed_event(message: dict[str, object], error: Exception) -> dict[str, object]:
    job_id = str(message.get("job_id", "unknown"))
    input_type = str(message.get("input_type", "hwpx"))
    stage = str(message.get("stage", "hwpx_extract"))
    error_code = "HWPX_REPLACE_WORKER_FAILED" if stage == "hwpx_replace" else "HWPX_EXTRACT_WORKER_FAILED"
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": error_code,
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
