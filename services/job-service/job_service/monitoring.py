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
    dependencies = _dependency_statuses(config, service)
    overall = _overall_status(list(dependencies.values()))
    return {
        "status": "ok" if overall in {"healthy", "degraded"} else "unhealthy",
        "overall_status": overall,
        "checked_at": _utc_now(),
        "service": config.service_name,
        "environment": config.app_env,
        "namespace": config.namespace,
        "dependencies": dependencies,
    }


def admin_health_payload(config: AppConfig, service: object) -> dict[str, object]:
    dependencies = _dependency_statuses(config, service)
    jobs = _list_jobs_or_empty(service)
    job_summary = job_state_summary_payload(jobs)
    queue_summary = queue_summary_payload(config)
    worker_summary = worker_summary_payload(service, jobs=jobs)
    overall_status = _admin_overall_status(
        dependencies=list(dependencies.values()),
        job_summary=job_summary,
        queue_summary=queue_summary,
    )
    return {
        "status": overall_status,
        "overall_status": overall_status,
        "checked_at": _utc_now(),
        "service": config.service_name,
        "environment": config.app_env,
        "namespace": config.namespace,
        "dependencies": dependencies,
        "job_summary": job_summary,
        "stale_running_count": job_summary["stale_running_count"],
        "retry_pending_count": job_summary["retry_pending_count"],
        "failed_job_count": job_summary["failed_job_count"],
        "recent_failed_jobs": job_summary["recent_failed_jobs"],
        "queue_summary": queue_summary,
        "worker_summary": worker_summary,
    }


def _dependency_statuses(config: AppConfig, service: object) -> dict[str, dict[str, object]]:
    return {
        "job_service": _job_service_status(config),
        "postgresql": _postgres_status(config, service),
        "rabbitmq": _rabbitmq_status(config),
        "minio": _minio_status(config),
    }


def worker_summary_payload(service: object, jobs: list[Job] | None = None) -> dict[str, object]:
    jobs = _list_jobs(service) if jobs is None else jobs
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
                "retry_pending": 0,
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
            seen = _latest_iso(
                state.started_at,
                state.completed_at,
                state.last_heartbeat_at,
                state.reconciled_at,
            )
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
        elif int(counts.get("retry_pending", 0)) > 0:
            summary["status"] = "retry_pending"
        elif int(counts.get("completed", 0)) > 0:
            summary["status"] = "observed"

    return {
        "status": "ok",
        "source": "job_stage_events",
        "heartbeat_available": False,
        "note": "Worker heartbeat is not implemented yet; this summary is derived from job stage state.",
        "workers": list(summaries.values()),
    }


def job_state_summary_payload(jobs: list[Job]) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    by_status: dict[str, int] = {}
    by_current_stage: dict[str, int] = {}
    stale_running: list[dict[str, object]] = []
    retry_pending: list[dict[str, object]] = []
    failed_jobs: list[Job] = []

    for job in jobs:
        by_status[job.status] = by_status.get(job.status, 0) + 1
        by_current_stage[job.current_stage] = by_current_stage.get(job.current_stage, 0) + 1
        if job.status == "failed":
            failed_jobs.append(job)
        for stage, state in job.stages.items():
            if state.status != "running" or state.lease_until is None or state.lease_until > now:
                if state.status == "retry_pending":
                    retry_pending.append(
                        {
                            "job_id": job.job_id,
                            "input_type": job.input_type,
                            "stage": stage,
                            "attempt": state.attempts,
                            "max_attempts": state.max_attempts,
                            "next_retry_at": state.next_retry_at.isoformat()
                            if state.next_retry_at
                            else None,
                            "retry_backoff_seconds": state.retry_backoff_seconds,
                            "last_error": state.last_error,
                            "last_reconcile_reason": state.last_reconcile_reason,
                        }
                    )
                continue
            stale_running.append(
                {
                    "job_id": job.job_id,
                    "input_type": job.input_type,
                    "stage": stage,
                    "attempt": state.attempts,
                    "max_attempts": state.max_attempts,
                    "lease_until": state.lease_until.isoformat(),
                    "last_heartbeat_at": state.last_heartbeat_at.isoformat()
                    if state.last_heartbeat_at
                    else None,
                    "last_reconcile_reason": state.last_reconcile_reason,
                }
            )

    recent_failed = sorted(failed_jobs, key=lambda job: job.updated_at, reverse=True)[:5]
    return {
        "total_jobs": len(jobs),
        "by_status": by_status,
        "by_current_stage": by_current_stage,
        "running_job_count": by_status.get("running", 0),
        "failed_job_count": by_status.get("failed", 0),
        "stale_running_count": len(stale_running),
        "stale_running_stages": stale_running,
        "retry_pending_count": len(retry_pending),
        "retry_pending_stages": retry_pending,
        "recent_failed_jobs": [
            {
                "job_id": job.job_id,
                "input_type": job.input_type,
                "status": job.status,
                "current_stage": job.current_stage,
                "error_stage": job.error_stage,
                "error_message": job.error_message,
                "updated_at": job.updated_at.isoformat(),
            }
            for job in recent_failed
        ],
    }


def queue_summary_payload(config: AppConfig) -> dict[str, object]:
    queues = _configured_queues(config)
    if not _rabbitmq_required(config):
        return {
            "status": "skipped",
            "reason": "RabbitMQ is not enabled for this job-service process",
            "metric_source": "configured_queue_names",
            "unacked_count_available": False,
            "queue_count": len(queues),
            "unhealthy_count": 0,
            "missing_count": 0,
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
        "metric_source": "amqp_passive_declare",
        "unacked_count_available": False,
        "queue_count": len(results),
        "unhealthy_count": len(errors),
        "missing_count": len(missing),
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
                "unacked_count": None,
                "metric_source": "amqp_passive_declare",
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
            "unacked_count": None,
            "metric_source": "amqp_passive_declare",
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
        "unacked_count": None,
        "metric_source": "configured_queue_names",
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


def _admin_overall_status(
    *,
    dependencies: list[dict[str, object]],
    job_summary: dict[str, object],
    queue_summary: dict[str, object],
) -> str:
    dependency_status = _overall_status(dependencies)
    if dependency_status == "unhealthy":
        return "unhealthy"
    if int(job_summary.get("stale_running_count", 0)) > 0:
        return "degraded"
    if int(job_summary.get("retry_pending_count", 0)) > 0:
        return "degraded"
    if int(job_summary.get("failed_job_count", 0)) > 0:
        return "degraded"
    if queue_summary.get("status") == "unhealthy":
        return "unhealthy"
    if queue_summary.get("status") == "degraded":
        return "degraded"
    if dependency_status == "degraded":
        return "degraded"
    return "healthy"


def _list_jobs(service: object) -> list[Job]:
    list_jobs = getattr(service, "list_jobs", None)
    if callable(list_jobs):
        return list(list_jobs())
    repository = getattr(service, "repository")
    return list(repository.list())


def _list_jobs_or_empty(service: object) -> list[Job]:
    try:
        return _list_jobs(service)
    except Exception:
        return []


def _latest_iso(*values: datetime | None) -> str | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present).isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
