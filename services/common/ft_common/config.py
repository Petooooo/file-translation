"""Environment-driven configuration shared by service skeletons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DEFAULT_COMMAND_QUEUES = {
    "pdf2docx": "q.commands.pdf2docx",
    "docx_extract": "q.commands.docx_extract",
    "docx_translate": "q.commands.docx_translate",
    "docx_replace": "q.commands.docx_replace",
    "docx_export": "q.commands.docx_export",
    "docx_marker": "q.commands.docx_marker",
    "pdf2hwpx": "q.commands.pdf2hwpx",
    "hwpx_extract": "q.commands.hwpx_extract",
    "hwpx_translate": "q.commands.hwpx_translate",
    "hwpx_replace": "q.commands.hwpx_replace",
    "hwpx_export": "q.commands.hwpx_export",
    "email_send": "q.commands.email_send",
}

DEFAULT_EVENT_QUEUES = {
    "stage_completed": "q.events.stage_completed",
    "stage_failed": "q.events.stage_failed",
    "progress": "q.events.progress",
}


@dataclass(frozen=True)
class AppConfig:
    service_name: str
    service_kind: str
    stage: str | None
    app_env: str
    namespace: str
    log_level: str
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_vhost: str
    rabbitmq_username: str
    rabbitmq_password: str
    minio_endpoint: str
    minio_bucket: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    translation_provider: str
    translation_api_base_url: str
    translation_api_timeout_seconds: int
    pdf2docx_image: str
    pdf2docx_enable_reports: bool
    job_service_command_publisher: str
    job_service_event_consumer: str
    command_queues: dict[str, str]
    event_queues: dict[str, str]

    def safe_dict(self) -> dict[str, object]:
        return {
            "service_name": self.service_name,
            "service_kind": self.service_kind,
            "stage": self.stage,
            "app_env": self.app_env,
            "namespace": self.namespace,
            "log_level": self.log_level,
            "rabbitmq": {
                "host": self.rabbitmq_host,
                "port": self.rabbitmq_port,
                "vhost": self.rabbitmq_vhost,
                "username_configured": bool(self.rabbitmq_username),
                "password_configured": bool(self.rabbitmq_password),
            },
            "minio": {
                "endpoint": self.minio_endpoint,
                "bucket": self.minio_bucket,
            },
            "postgres": {
                "host": self.postgres_host,
                "port": self.postgres_port,
                "db": self.postgres_db,
            },
            "translation": {
                "provider": self.translation_provider,
                "api_base_url": self.translation_api_base_url,
                "timeout_seconds": self.translation_api_timeout_seconds,
            },
            "pdf2docx": {
                "image": self.pdf2docx_image,
                "enable_reports": self.pdf2docx_enable_reports,
            },
            "queues": {
                "commands": self.command_queues,
                "events": self.event_queues,
            },
            "job_service": {
                "command_publisher": self.job_service_command_publisher,
                "event_consumer": self.job_service_event_consumer,
            },
        }


def _env(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name)
    if value is None or value == "":
        return default
    return value


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    value = _env(env, name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _bool_env(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _env(env, name, "true" if default else "false")
    value = raw.lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _queue_env_name(prefix: str, key: str) -> str:
    return f"{prefix}_{key.upper()}"


def load_config(
    service_name: str,
    service_kind: str,
    stage: str | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    import os

    source = os.environ if env is None else env

    command_queues = {
        key: _env(source, _queue_env_name("QUEUE_COMMANDS", key), value)
        for key, value in DEFAULT_COMMAND_QUEUES.items()
    }
    event_queues = {
        key: _env(source, _queue_env_name("QUEUE_EVENTS", key), value)
        for key, value in DEFAULT_EVENT_QUEUES.items()
    }

    return AppConfig(
        service_name=_env(source, "SERVICE_NAME", service_name),
        service_kind=service_kind,
        stage=stage,
        app_env=_env(source, "APP_ENV", "local"),
        namespace=_env(source, "NAMESPACE", "file-translation"),
        log_level=_env(source, "LOG_LEVEL", "INFO"),
        rabbitmq_host=_env(source, "RABBITMQ_HOST", "rabbitmq"),
        rabbitmq_port=_int_env(source, "RABBITMQ_PORT", 5672),
        rabbitmq_vhost=_env(source, "RABBITMQ_VHOST", "/"),
        rabbitmq_username=_env(source, "RABBITMQ_USERNAME", ""),
        rabbitmq_password=_env(source, "RABBITMQ_PASSWORD", ""),
        minio_endpoint=_env(source, "MINIO_ENDPOINT", "http://minio:9000"),
        minio_bucket=_env(source, "MINIO_BUCKET", "file-translation"),
        postgres_host=_env(source, "POSTGRES_HOST", "postgresql"),
        postgres_port=_int_env(source, "POSTGRES_PORT", 5432),
        postgres_db=_env(source, "POSTGRES_DB", "file_translation"),
        translation_provider=_env(source, "TRANSLATION_PROVIDER", "mock"),
        translation_api_base_url=_env(source, "TRANSLATION_API_BASE_URL", "http://translation-api"),
        translation_api_timeout_seconds=_int_env(source, "TRANSLATION_API_TIMEOUT_SECONDS", 30),
        pdf2docx_image=_env(source, "PDF2DOCX_IMAGE", "petoo/pdf2docx:0.5.13-py311-static"),
        pdf2docx_enable_reports=_bool_env(source, "PDF2DOCX_ENABLE_REPORTS", False),
        job_service_command_publisher=_env(source, "JOB_SERVICE_COMMAND_PUBLISHER", "memory").lower(),
        job_service_event_consumer=_env(source, "JOB_SERVICE_EVENT_CONSUMER", "disabled").lower(),
        command_queues=command_queues,
        event_queues=event_queues,
    )
