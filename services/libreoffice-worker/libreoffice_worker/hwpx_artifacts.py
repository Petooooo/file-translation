"""Artifact key and event flow for libreoffice-worker hwpx_export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ft_common.minio_store import ArtifactStore
from libreoffice_worker.hwpx_export import export_hwpx_artifacts


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_CONTENT_TYPE = "application/pdf"
HWPX_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class HwpxExportWorkerCommand:
    job_id: str
    input_type: str
    stage: str
    object_prefix: str
    attempt: int = 1
    input_object_key: str | None = None
    final_docx_object_key: str | None = None
    final_pdf_object_key: str | None = None
    final_hwpx_object_key: str | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "HwpxExportWorkerCommand":
        command = cls(
            job_id=str(message["job_id"]),
            input_type=str(message["input_type"]),
            stage=str(message["stage"]),
            object_prefix=str(message["object_prefix"]).strip("/"),
            attempt=int(message.get("attempt", 1)),
            input_object_key=_optional_str(message.get("input_object_key")),
            final_docx_object_key=_optional_str(message.get("final_docx_object_key")),
            final_pdf_object_key=_optional_str(message.get("final_pdf_object_key")),
            final_hwpx_object_key=_optional_str(message.get("final_hwpx_object_key")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.input_type != "hwpx":
            raise ValueError(f"libreoffice-worker hwpx_export requires input_type 'hwpx', got {self.input_type!r}")
        if self.stage != "hwpx_export":
            raise ValueError(f"libreoffice-worker requires stage='hwpx_export', got {self.stage!r}")
        if not self.object_prefix:
            raise ValueError("object_prefix is required")


@dataclass(frozen=True)
class HwpxExportArtifactKeys:
    translated_hwpx: str
    final_docx: str
    final_pdf: str
    final_hwpx: str

    def completed_outputs(self) -> dict[str, str]:
        return {
            "final_docx": self.final_docx,
            "final_pdf": self.final_pdf,
            "final_hwpx": self.final_hwpx,
        }


def artifact_keys_for(command: HwpxExportWorkerCommand) -> HwpxExportArtifactKeys:
    prefix = command.object_prefix
    return HwpxExportArtifactKeys(
        translated_hwpx=command.input_object_key or f"{prefix}/04_replace/translated.hwpx",
        final_docx=command.final_docx_object_key or f"{prefix}/05_export/final.docx",
        final_pdf=command.final_pdf_object_key or f"{prefix}/05_export/final.pdf",
        final_hwpx=command.final_hwpx_object_key or f"{prefix}/06_hwpx/final.hwpx",
    )


def process_hwpx_export_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
    h2o_export_enabled: bool = False,
) -> dict[str, object]:
    command = HwpxExportWorkerCommand.from_message(message)
    keys = artifact_keys_for(command)
    work_dir = work_root / _safe_segment(command.job_id)
    input_hwpx_path = work_dir / "translated.hwpx"
    final_hwpx_path = work_dir / "final.hwpx"
    final_docx_path = work_dir / "final.docx"
    final_pdf_path = work_dir / "final.pdf"

    store.download_file(keys.translated_hwpx, input_hwpx_path)
    export_hwpx_artifacts(
        input_hwpx_path=input_hwpx_path,
        final_hwpx_path=final_hwpx_path,
        final_docx_path=final_docx_path,
        final_pdf_path=final_pdf_path,
        h2o_export_enabled=h2o_export_enabled,
    )
    store.upload_file(keys.final_docx, final_docx_path, DOCX_CONTENT_TYPE)
    store.upload_file(keys.final_pdf, final_pdf_path, PDF_CONTENT_TYPE)
    store.upload_file(keys.final_hwpx, final_hwpx_path, HWPX_CONTENT_TYPE)

    return stage_completed_event(command, keys.completed_outputs())


def stage_completed_event(command: HwpxExportWorkerCommand, outputs: dict[str, str]) -> dict[str, object]:
    return {
        "event_type": "stage.completed",
        "job_id": command.job_id,
        "input_type": command.input_type,
        "stage": command.stage,
        "outputs": outputs,
    }


def stage_failed_event(message: dict[str, object], error: Exception) -> dict[str, object]:
    job_id = str(message.get("job_id", "unknown"))
    input_type = str(message.get("input_type", "hwpx"))
    stage = str(message.get("stage", "hwpx_export"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": "HWPX_EXPORT_WORKER_FAILED",
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
