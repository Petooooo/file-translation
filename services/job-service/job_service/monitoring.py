"""Monitoring payloads for job-service readiness and admin operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ft_common.config import AppConfig
from ft_common.minio_store import MinioConnectionSettings, build_minio_client
from job_service.models import Job
from job_service.rabbitmq import RabbitMQConnectionSettings, pika_blocking_connection


COMMAND_STAGE_WORKERS = {
    "pdf2docx": "pdf2docx-worker",
    "docx_extract": "docx-extract-worker",
    "docx_translate": "translate-worker",
    "docx_replace": "docx-replace-worker",
    "docx_export": "libreoffice-worker",
    "docx_marker": "libreoffice-worker",
    "pdf2hwpx": "pdf2hwpx-worker",
    "hwpx_extract": "hwpx-worker",
    "hwpx_translate": "translate-worker",
    "hwpx_replace": "hwpx-worker",
    "hwpx_export": "libreoffice-worker",
    "email_send": "email-worker",
}


def readiness_payload(config: AppConfig, service: object) -> dict[str, object]:
    payload = admin_health_payload(config, service)
    overall = str(payload["overall_status"])
    return {
        **payload,
        "status": "ok" if overall in {"healthy", "degraded"} else "unhealthy",
    }


def admin_health_payload(config: AppConfig, service: object) -> dict[str, object]:
    dependencies = {
        "job_service": _job_service_status(config),
        "postgresql": _postgres_status(config, service),
        "rabbitmq": _rabbitmq_status(config),
        "minio": _minio_status(config),
    }
    return {
        "status": _overall_status(list(dependencies.values())),
        "overall_status": _overall_status(list(dependencies.values())),
        "checked_at": _utc_now(),
        "service": config.service_name,
        "environment": config.app_env,
        "namespace": config.namespace,
        "dependencies": dependencies,
    }


def worker_summary_payload(service: object) -> dict[str, object]:
    jobs = _list_jobs(service)
    summaries: dict[str, dict[str, object]] = {}
    for stage, worker_name in COMMAND_STAGE_WORKERS.items():
        summaries[stage] = {
            "worker": worker_name,
            "handled_stage": stage,
            "status": "no_data",
            "last_seen": None,
            "last_error": None,
            "counts": {
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
            },
        }

    for job in jobs:
        for stage, state in job.stages.items():
            if stage not in summaries:
                continue
            summary = summaries[stage]
            counts = summary["counts"]
            if isinstance(counts, dict):
                counts[state.status] = int(counts.get(state.status, 0)) + 1
            seen = _latest_iso(state.started_at, state.completed_at, job.updated_at)
            if seen and (summary["last_seen"] is None or str(summary["last_seen"]) < seen):
                summary["last_seen"] = seen
            if state.error_message:
                summary["last_error"] = state.error_message

    for summary in summaries.values():
        counts = summary["counts"]
        if not isinstance(counts, dict):
            continue
        if int(counts.get("failed", 0)) > 0:
            summary["status"] = "failed"
        elif int(counts.get("running", 0)) > 0:
            summary["status"] = "running"
        elif int(counts.get("completed", 0)) > 0:
            summary["status"] = "observed"

    return {
        "status": "ok",
        "source": "job_stage_events",
        "heartbeat_available": False,
        "note": "Worker heartbeat is not implemented yet; this summary is derived from job stage state.",
        "workers": list(summaries.values()),
    }


def queue_summary_payload(config: AppConfig) -> dict[str, object]:
    queues = _configured_queues(config)
    if not _rabbitmq_required(config):
        return {
            "status": "skipped",
            "reason": "RabbitMQ is not enabled for this job-service process",
            "queues": [_queue_skipped(queue) for queue in queues],
        }

    results = [_queue_status(config, queue) for queue in queues]
    missing = [queue for queue in results if queue["exists"] is False]
    errors = [queue for queue in results if queue.get("status") == "unhealthy"]
    if errors:
        status = "unhealthy"
    elif missing:
        status = "degraded"
    else:
        status = "healthy"
    return {
        "status": status,
        "checked_at": _utc_now(),
        "queues": results,
    }


def _job_service_status(config: AppConfig) -> dict[str, object]:
    return {
        "status": "healthy",
        "required": True,
        "service": config.service_name,
    }


def _postgres_status(config: AppConfig, service: object) -> dict[str, object]:
    required = config.job_service_repository == "postgres"
    if not required:
        return {"status": "skipped", "required": False, "mode": config.job_service_repository}
    try:
        _list_jobs(service)
    except Exception as exc:
        return {
            "status": "unhealthy",
            "required": True,
            "mode": config.job_service_repository,
            "error": str(exc),
        }
    return {
        "status": "healthy",
        "required": True,
        "mode": config.job_service_repository,
        "host": config.postgres_host,
        "port": config.postgres_port,
        "db": config.postgres_db,
    }


def _rabbitmq_status(config: AppConfig) -> dict[str, object]:
    required = _rabbitmq_required(config)
    if not required:
        return {
            "status": "skipped",
            "required": False,
            "command_publisher": config.job_service_command_publisher,
            "event_consumer": config.job_service_event_consumer,
        }
    try:
        connection = pika_blocking_connection(RabbitMQConnectionSettings.from_config(config))
        connection.close()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "required": True,
            "host": config.rabbitmq_host,
            "port": config.rabbitmq_port,
            "vhost": config.rabbitmq_vhost,
            "error": str(exc),
        }
    return {
        "status": "healthy",
        "required": True,
        "host": config.rabbitmq_host,
        "port": config.rabbitmq_port,
        "vhost": config.rabbitmq_vhost,
    }


def _minio_status(config: AppConfig) -> dict[str, object]:
    required = bool(config.minio_access_key and config.minio_secret_key)
    if not required:
        return {
            "status": "skipped",
            "required": False,
            "endpoint": config.minio_endpoint,
            "bucket": config.minio_bucket,
            "reason": "MINIO_ACCESS_KEY and MINIO_SECRET_KEY are not configured",
        }
    try:
        settings = MinioConnectionSettings.from_config(config)
        client = build_minio_client(settings)
        exists = bool(client.bucket_exists(settings.bucket))
    except Exception as exc:
        return {
            "status": "unhealthy",
            "required": True,
            "endpoint": config.minio_endpoint,
            "bucket": config.minio_bucket,
            "error": str(exc),
        }
    return {
        "status": "healthy" if exists else "degraded",
        "required": True,
        "endpoint": config.minio_endpoint,
        "bucket": config.minio_bucket,
        "bucket_exists": exists,
    }


def _queue_status(config: AppConfig, queue: dict[str, str]) -> dict[str, object]:
    try:
        connection = pika_blocking_connection(RabbitMQConnectionSettings.from_config(config))
        try:
            channel = connection.channel()
            result = channel.queue_declare(queue=queue["name"], passive=True)
            method = result.method
            return {
                **queue,
                "status": "healthy",
                "exists": True,
                "message_count": int(getattr(method, "message_count", 0)),
                "consumer_count": int(getattr(method, "consumer_count", 0)),
            }
        finally:
            connection.close()
    except Exception as exc:
        return {
            **queue,
            "status": "unhealthy",
            "exists": False,
            "message_count": None,
            "consumer_count": None,
            "error": str(exc),
        }


def _configured_queues(config: AppConfig) -> list[dict[str, str]]:
    queues = [
        {"kind": "command", "stage": stage, "name": name}
        for stage, name in config.command_queues.items()
    ]
    queues.extend(
        {"kind": "event", "stage": stage, "name": name}
        for stage, name in config.event_queues.items()
    )
    return queues


def _queue_skipped(queue: dict[str, str]) -> dict[str, object]:
    return {
        **queue,
        "status": "skipped",
        "exists": None,
        "message_count": None,
        "consumer_count": None,
    }


def _rabbitmq_required(config: AppConfig) -> bool:
    return (
        config.job_service_command_publisher == "rabbitmq"
        or config.job_service_event_consumer == "rabbitmq"
    )


def _overall_status(dependencies: list[dict[str, object]]) -> str:
    required = [dependency for dependency in dependencies if dependency.get("required") is True]
    if any(dependency.get("status") == "unhealthy" for dependency in required):
        return "unhealthy"
    if any(dependency.get("status") == "degraded" for dependency in required):
        return "degraded"
    optional = [dependency for dependency in dependencies if dependency.get("required") is False]
    if any(dependency.get("status") in {"unhealthy", "degraded"} for dependency in optional):
        return "degraded"
    return "healthy"


def _list_jobs(service: object) -> list[Job]:
    list_jobs = getattr(service, "list_jobs", None)
    if callable(list_jobs):
        return list(list_jobs())
    repository = getattr(service, "repository")
    return list(repository.list())


def _latest_iso(*values: datetime | None) -> str | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present).isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
