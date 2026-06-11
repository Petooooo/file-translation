"""Artifact key and event flow for pdf2hwpx-worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ft_common.minio_store import ArtifactStore
from pdf2hwpx_worker.placeholder import generate_placeholder_hwpx


HWPX_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class Pdf2HwpxWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    attempt: int = 1
    input_object_key: str | None = None
    output_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "Pdf2HwpxWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
            output_object_key=_optional_str(message.get("output_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type not in {"pdf", "docx"}:
            raise ValueError(f"pdf2hwpx-worker requires input_type 'pdf' or 'docx', got {self.input_type!r}")
        if self.stage != "pdf2hwpx":
            raise ValueError(f"pdf2hwpx-worker requires stage='pdf2hwpx', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class Pdf2HwpxArtifactKeys:
    marker_docx: str
    final_hwpx: str

    def completed_outputs(self) -> dict[str, str]:
        return {"final_hwpx": self.final_hwpx}


def artifact_keys_for(command: Pdf2HwpxWorkerCommand) -> Pdf2HwpxArtifactKeys:
    prefix = command.object_prefix
    return Pdf2HwpxArtifactKeys(
        marker_docx=command.input_object_key or f"{prefix}/05_export/marker.docx",
        final_hwpx=command.output_object_key or f"{prefix}/06_hwpx/final.hwpx",
    )


def process_pdf2hwpx_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
) -> dict[str, object]:
    command = Pdf2HwpxWorkerCommand.from_message(message)
    keys = artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    marker_docx_path = work_dir / "marker.docx"
    output_hwpx_path = work_dir / "final.hwpx"

    store.download_file(keys.marker_docx, marker_docx_path)
    generate_placeholder_hwpx(
        marker_docx_path=marker_docx_path,
        output_hwpx_path=output_hwpx_path,
        job_id=command.job_id,
        input_type=command.input_type,
        object_prefix=command.object_prefix,
    )
    store.upload_file(keys.final_hwpx, output_hwpx_path, HWPX_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: Pdf2HwpxWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
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
    stage = str(message.get("stage", "pdf2hwpx"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "PDF2HWPX_WORKER_FAILED",
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
