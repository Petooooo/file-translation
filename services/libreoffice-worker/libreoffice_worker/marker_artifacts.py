"""Artifact key and event flow for libreoffice-worker docx_marker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ft_common.minio_store import ArtifactStore
from libreoffice_worker.marker import mark_docx_spaces


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class DocxMarkerWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    attempt: int = 1
    input_object_key: str | None = None
    marker_docx_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "DocxMarkerWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
            marker_docx_object_key=_optional_str(message.get("marker_docx_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type not in {"pdf", "docx"}:
            raise ValueError(f"libreoffice-worker docx_marker requires input_type 'pdf' or 'docx', got {self.input_type!r}")
        if self.stage != "docx_marker":
            raise ValueError(f"libreoffice-worker requires stage='docx_marker', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class DocxMarkerArtifactKeys:
    final_docx: str
    marker_docx: str

    def completed_outputs(self) -> dict[str, str]:
        return {"marker_docx": self.marker_docx}


def artifact_keys_for(command: DocxMarkerWorkerCommand) -> DocxMarkerArtifactKeys:
    prefix = command.object_prefix
    return DocxMarkerArtifactKeys(
        final_docx=command.input_object_key or f"{prefix}/05_export/final.docx",
        marker_docx=command.marker_docx_object_key or f"{prefix}/05_export/marker.docx",
    )


def process_docx_marker_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
    marker: str = "¡",
) -> dict[str, object]:
    command = DocxMarkerWorkerCommand.from_message(message)
    keys = artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_docx_path = work_dir / "final.docx"
    marker_docx_path = work_dir / "marker.docx"

    store.download_file(keys.final_docx, input_docx_path)
    mark_docx_spaces(
        input_docx_path=input_docx_path,
        marker_docx_path=marker_docx_path,
        marker=marker,
    )
    store.upload_file(keys.marker_docx, marker_docx_path, DOCX_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: DocxMarkerWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
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
    stage = str(message.get("stage", "docx_marker"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "DOCX_MARKER_WORKER_FAILED",
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
