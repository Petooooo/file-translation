"""In-memory job metadata model for orchestration tests and early API work."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

JOB_STATUSES = {
    "queued",
    "running",
    "cancel_requested",
    "cancelled",
    "completed",
    "failed",
    "expired",
}

TERMINAL_STATUSES = {"cancelled", "completed", "failed", "expired"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@dataclass
class StageState:
    stage: str
    status: str = "pending"
    attempts: int = 0
    outputs: dict[str, str] = field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "attempts": self.attempts,
            "outputs": self.outputs,
            "error_message": self.error_message,
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
        }


@dataclass
class Job:
    job_id: str
    user_id: str
    file_id: str
    input_type: str
    source_lang: str
    target_lang: str
    status: str
    current_stage: str
    pipeline_route: list[str]
    object_prefix: str
    original_filename: str
    input_object_key: str
    final_docx_key: str | None = None
    final_pdf_key: str | None = None
    final_hwpx_key: str | None = None
    translated_hwpx_key: str | None = None
    error_stage: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    stages: dict[str, StageState] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    progress: dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def is_cancel_blocked(self) -> bool:
        return self.status in {"cancel_requested", "cancelled"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "file_id": self.file_id,
            "input_type": self.input_type,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "status": self.status,
            "current_stage": self.current_stage,
            "pipeline_route": self.pipeline_route,
            "object_prefix": self.object_prefix,
            "original_filename": self.original_filename,
            "input_object_key": self.input_object_key,
            "final_docx_key": self.final_docx_key,
            "final_pdf_key": self.final_pdf_key,
            "final_hwpx_key": self.final_hwpx_key,
            "translated_hwpx_key": self.translated_hwpx_key,
            "error_stage": self.error_stage,
            "error_message": self.error_message,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "completed_at": iso(self.completed_at),
            "cancel_requested_at": iso(self.cancel_requested_at),
            "stages": {stage: state.to_dict() for stage, state in self.stages.items()},
            "artifacts": self.artifacts,
            "progress": self.progress,
        }
