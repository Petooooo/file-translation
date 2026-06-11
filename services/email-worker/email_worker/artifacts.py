"""Artifact, provider, and event flow for email-worker."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ft_common.config import AppConfig
from ft_common.minio_store import ArtifactStore
from email_worker.job_service_client import JobServiceClient
from email_worker.provider import Attachment, MailProvider, MailSendResult


JSON_CONTENT_TYPE = "application/json"
ATTACHMENT_ARTIFACT_ORDER = ("final_docx", "final_pdf", "final_hwpx", "translated_hwpx")


class EmailSendError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        retryable: bool = False,
        input_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
        self.input_type = input_type


@dataclass(frozen=True)
class EmailSendCommand:
    job_id: str
    stage: str
    input_type: str | None = None
    object_prefix: str | None = None
    attempt: int = 1
    uid: str | None = None
    to: str | None = None
    subject: str | None = None
    body: str | None = None
    email_report_object_key: str | None = None
    attachments: list[Attachment] | None = None

    @classmethod
    def from_message(cls, message: dict[str, object]) -> "EmailSendCommand":
        command = cls(
            job_id=str(message["job_id"]),
            stage=str(message.get("stage", "email_send")),
            input_type=_optional_str(message.get("input_type")),
            object_prefix=_optional_str(message.get("object_prefix")),
            attempt=int(message.get("attempt", 1)),
            uid=_optional_str(message.get("uid")),
            to=_optional_str(message.get("to")),
            subject=_optional_str(message.get("subject")),
            body=_optional_str(message.get("body")),
            email_report_object_key=_optional_str(message.get("email_report_object_key")),
            attachments=_attachments_from_message(message.get("attachments")),
        )
        command.validate()
        return command

    def validate(self) -> None:
        if self.stage != "email_send":
            raise ValueError(f"email-worker requires stage='email_send', got {self.stage!r}")
        if self.input_type is not None and self.input_type not in {"pdf", "docx", "hwpx"}:
            raise ValueError(f"email-worker requires input_type 'pdf', 'docx', or 'hwpx', got {self.input_type!r}")


@dataclass(frozen=True)
class EmailRequest:
    uid: str
    to: str
    subject: str
    body: str
    attachments: list[Attachment]
    metadata: dict[str, object]
    input_type: str
    object_prefix: str
    report_object_key: str


def process_email_send_command(
    message: dict[str, object],
    *,
    store: ArtifactStore,
    work_root: Path,
    provider: MailProvider,
    job_service_client: JobServiceClient,
    config: AppConfig,
) -> dict[str, object]:
    command = EmailSendCommand.from_message(message)
    sendability = job_service_client.get_sendability(command.job_id)
    try:
        request_payload = build_email_request(command, sendability, config)
    except EmailSendError as exc:
        return stage_failed_event(message, exc)

    try:
        result = provider.send_mail(
            uid=request_payload.uid,
            to=request_payload.to,
            subject=request_payload.subject,
            body=request_payload.body,
            attachments=request_payload.attachments,
            metadata=request_payload.metadata,
        )
    except Exception as exc:
        raise EmailSendError(
            "EMAIL_SEND_FAILED",
            str(exc),
            retryable=False,
            input_type=request_payload.input_type,
        ) from exc

    report = build_email_report(
        command=command,
        request_payload=request_payload,
        result=result,
    )
    report_path = work_root / _safe_segment(command.job_id) / "email_report.json"
    write_email_report(report, report_path)
    store.upload_file(request_payload.report_object_key, report_path, JSON_CONTENT_TYPE)

    return stage_completed_event(
        command=command,
        input_type=request_payload.input_type,
        outputs={"email_report": request_payload.report_object_key},
        metrics={"provider": result.provider},
    )


def build_email_request(
    command: EmailSendCommand,
    sendability: dict[str, object],
    config: AppConfig,
) -> EmailRequest:
    input_type = command.input_type or _optional_str(sendability.get("input_type")) or "docx"
    if not config.email_send_enabled:
        raise EmailSendError("EMAIL_SEND_DISABLED", "email sending is disabled", input_type=input_type)
    if sendability.get("sendable") is not True:
        reason = _optional_str(sendability.get("reason")) or "job is not sendable"
        raise EmailSendError("EMAIL_NOT_SENDABLE", reason, input_type=input_type)

    object_prefix = (command.object_prefix or _optional_str(sendability.get("object_prefix")) or "").strip("/")
    if not object_prefix and not command.email_report_object_key:
        raise EmailSendError("EMAIL_OBJECT_PREFIX_MISSING", "object_prefix is required", input_type=input_type)

    attachments = command.attachments or _attachments_from_sendability(sendability)
    if not attachments:
        raise EmailSendError("EMAIL_ATTACHMENTS_MISSING", "no final artifacts are available to email", input_type=input_type)

    uid = command.uid or _optional_str(sendability.get("user_id")) or command.job_id
    to = command.to or _optional_str(sendability.get("to")) or _optional_str(sendability.get("recipient_email"))
    if not to:
        to = f"{uid}@example.local"

    subject = command.subject or "Translated files are ready"
    body = command.body or "Translated files are ready."
    report_object_key = command.email_report_object_key or f"{object_prefix}/reports/email_report.json"
    metadata = {
        "job_id": command.job_id,
        "input_type": input_type,
        "object_prefix": object_prefix,
        "status": sendability.get("status"),
        "current_stage": sendability.get("current_stage"),
        "email_from": config.email_from,
    }

    return EmailRequest(
        uid=uid,
        to=to,
        subject=subject,
        body=body,
        attachments=attachments,
        metadata=metadata,
        input_type=input_type,
        object_prefix=object_prefix,
        report_object_key=report_object_key,
    )


def build_email_report(
    *,
    command: EmailSendCommand,
    request_payload: EmailRequest,
    result: MailSendResult,
) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": "1.0",
        "job_id": command.job_id,
        "provider": result.provider,
        "status": result.status,
        "to": request_payload.to,
        "subject": request_payload.subject,
        "attachments": [_attachment_report_value(attachment) for attachment in request_payload.attachments],
        "sent_at": result.sent_at,
    }
    if result.provider_message_id:
        report["provider_message_id"] = result.provider_message_id
    return report


def write_email_report(report: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def stage_completed_event(
    *,
    command: EmailSendCommand,
    input_type: str,
    outputs: dict[str, str],
    metrics: dict[str, object],
) -> dict[str, object]:
    return {
        "event_type": "stage.completed",
        "job_id": command.job_id,
        "input_type": input_type,
        "stage": command.stage,
        "outputs": outputs,
        "metrics": metrics,
    }


def stage_failed_event(message: dict[str, object], error: Exception) -> dict[str, object]:
    job_id = str(message.get("job_id", "unknown"))
    input_type = _optional_str(message.get("input_type")) or getattr(error, "input_type", None) or "docx"
    stage = str(message.get("stage", "email_send"))
    return {
        "event_type": "stage.failed",
        "job_id": job_id,
        "input_type": input_type,
        "stage": stage,
        "error_code": getattr(error, "error_code", "EMAIL_SEND_FAILED"),
        "error_message": str(error),
        "retryable": bool(getattr(error, "retryable", False)),
    }


def event_queue_key(event: dict[str, object]) -> str:
    event_type = str(event.get("event_type", ""))
    if event_type == "stage.completed":
        return "stage_completed"
    if event_type == "stage.failed":
        return "stage_failed"
    return "progress"


def _attachments_from_sendability(sendability: dict[str, object]) -> list[Attachment]:
    artifacts = sendability.get("artifacts")
    if not isinstance(artifacts, dict):
        return []
    attachments: list[Attachment] = []
    seen: set[str] = set()
    for artifact_name in ATTACHMENT_ARTIFACT_ORDER:
        value = artifacts.get(artifact_name)
        if not isinstance(value, str) or value in seen:
            continue
        seen.add(value)
        attachments.append({"object_key": value, "artifact": artifact_name})
    return attachments


def _attachments_from_message(value: object) -> list[Attachment] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("attachments must be a list")
    attachments: list[Attachment] = []
    for item in value:
        if isinstance(item, str):
            attachments.append({"object_key": item})
        elif isinstance(item, dict):
            attachments.append({str(key): item[key] for key in item})
        else:
            raise ValueError("attachments entries must be strings or objects")
    return attachments


def _attachment_report_value(attachment: Attachment) -> str:
    for key in ("object_key", "local_path", "path"):
        value = attachment.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(attachment, ensure_ascii=False, sort_keys=True)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _safe_segment(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "job"
