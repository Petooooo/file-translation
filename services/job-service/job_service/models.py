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
    command_id: str | None = None
    claim_id: str | None = None
    idempotency_key: str | None = None
    claimed_by: str | None = None
    lease_until: datetime | None = None
    last_heartbeat_at: datetime | None = None
    max_attempts: int = 3
    progress: float = 0
    long_running: bool = False
    retryable: bool | None = None
    next_retry_at: datetime | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "attempts": self.attempts,
            "outputs": self.outputs,
            "error_message": self.error_message,
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
            "command_id": self.command_id,
            "claim_id": self.claim_id,
            "idempotency_key": self.idempotency_key,
            "claimed_by": self.claimed_by,
            "lease_until": iso(self.lease_until),
            "last_heartbeat_at": iso(self.last_heartbeat_at),
            "max_attempts": self.max_attempts,
            "progress": self.progress,
            "long_running": self.long_running,
            "retry_count": max(self.attempts - 1, 0),
            "retryable": self.retryable,
            "next_retry_at": iso(self.next_retry_at),
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageState":
        return cls(
            stage=str(payload["stage"]),
            status=str(payload.get("status", "pending")),
            attempts=int(payload.get("attempts", 0)),
            outputs={str(key): str(value) for key, value in dict(payload.get("outputs", {})).items()},
            error_message=_optional_str(payload.get("error_message")),
            started_at=_parse_datetime(payload.get("started_at")),
            completed_at=_parse_datetime(payload.get("completed_at")),
            command_id=_optional_str(payload.get("command_id")),
            claim_id=_optional_str(payload.get("claim_id")),
            idempotency_key=_optional_str(payload.get("idempotency_key")),
            claimed_by=_optional_str(payload.get("claimed_by")),
            lease_until=_parse_datetime(payload.get("lease_until")),
            last_heartbeat_at=_parse_datetime(payload.get("last_heartbeat_at")),
            max_attempts=int(payload.get("max_attempts", 3)),
            progress=float(payload.get("progress", 0) or 0),
            long_running=bool(payload.get("long_running", False)),
            retryable=_optional_bool(payload.get("retryable")),
            next_retry_at=_parse_datetime(payload.get("next_retry_at")),
            last_error=_optional_str(payload.get("last_error")),
        )


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

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Job":
        stages_payload = payload.get("stages", {})
        stages = {
            str(stage): StageState.from_dict(dict(state))
            for stage, state in dict(stages_payload).items()
        }
        return cls(
            job_id=str(payload["job_id"]),
            user_id=str(payload["user_id"]),
            file_id=str(payload["file_id"]),
            input_type=str(payload["input_type"]),
            source_lang=str(payload["source_lang"]),
            target_lang=str(payload["target_lang"]),
            status=str(payload["status"]),
            current_stage=str(payload["current_stage"]),
            pipeline_route=[str(stage) for stage in list(payload["pipeline_route"])],
            object_prefix=str(payload["object_prefix"]),
            original_filename=str(payload["original_filename"]),
            input_object_key=str(payload["input_object_key"]),
            final_docx_key=_optional_str(payload.get("final_docx_key")),
            final_pdf_key=_optional_str(payload.get("final_pdf_key")),
            final_hwpx_key=_optional_str(payload.get("final_hwpx_key")),
            translated_hwpx_key=_optional_str(payload.get("translated_hwpx_key")),
            error_stage=_optional_str(payload.get("error_stage")),
            error_message=_optional_str(payload.get("error_message")),
            created_at=_parse_datetime(payload.get("created_at")) or utc_now(),
            updated_at=_parse_datetime(payload.get("updated_at")) or utc_now(),
            completed_at=_parse_datetime(payload.get("completed_at")),
            cancel_requested_at=_parse_datetime(payload.get("cancel_requested_at")),
            stages=stages,
            artifacts={str(key): str(value) for key, value in dict(payload.get("artifacts", {})).items()},
            progress=dict(payload.get("progress", {})),
        )


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)
