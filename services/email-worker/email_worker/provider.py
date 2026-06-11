"""Mail provider abstraction for email-worker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from ft_common.config import AppConfig


Attachment = dict[str, object]


@dataclass(frozen=True)
class MailSendResult:
    provider: str
    status: str
    sent_at: str
    provider_message_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class MailProvider(Protocol):
    name: str

    def send_mail(
        self,
        *,
        uid: str,
        to: str,
        subject: str,
        body: str,
        attachments: list[Attachment],
        metadata: dict[str, object],
    ) -> MailSendResult:
        ...


@dataclass(frozen=True)
class MockMailProvider:
    name: str = "mock"

    def send_mail(
        self,
        *,
        uid: str,
        to: str,
        subject: str,
        body: str,
        attachments: list[Attachment],
        metadata: dict[str, object],
    ) -> MailSendResult:
        return MailSendResult(
            provider=self.name,
            status="sent",
            sent_at=_utc_now_iso(),
            provider_message_id=f"mock-{metadata.get('job_id', uid)}",
            metadata={
                "uid": uid,
                "attachment_count": len(attachments),
            },
        )


def build_mail_provider(config: AppConfig) -> MailProvider:
    provider = config.email_provider.lower()
    if provider == "mock":
        return MockMailProvider()
    if provider in {"smtp", "military_api"}:
        raise NotImplementedError(f"EMAIL_PROVIDER={provider!r} is documented but not implemented yet")
    raise ValueError(f"unsupported EMAIL_PROVIDER: {config.email_provider!r}")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
