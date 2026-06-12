"""Command publisher interface and in-memory implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ft_common.config import AppConfig
from job_service.models import Job


@dataclass(frozen=True)
class CommandEnvelope:
    queue: str
    message: dict[str, object]


class CommandPublisher(Protocol):
    def publish_command(self, job: Job, stage: str) -> CommandEnvelope:
        ...


class InMemoryCommandPublisher:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.published: list[CommandEnvelope] = []

    def publish_command(self, job: Job, stage: str) -> CommandEnvelope:
        envelope = build_command_envelope(self.config, job, stage)
        self.published.append(envelope)
        return envelope


def build_command_envelope(config: AppConfig, job: Job, stage: str) -> CommandEnvelope:
    try:
        queue = config.command_queues[stage]
    except KeyError as exc:
        raise ValueError(f"no command queue configured for stage {stage!r}") from exc

    stage_state = job.stages[stage]
    command_id = f"{job.job_id}:{stage}:{stage_state.attempts}"
    idempotency_key = command_id
    message: dict[str, object] = {
        "job_id": job.job_id,
        "input_type": job.input_type,
        "stage": stage,
        "attempt": stage_state.attempts,
        "command_id": command_id,
        "idempotency_key": idempotency_key,
        "lease_seconds": config.stage_claim_lease_seconds,
        "max_attempts": stage_state.max_attempts or config.stage_claim_max_attempts,
        "object_prefix": job.object_prefix,
        "source_lang": job.source_lang,
        "target_lang": job.target_lang,
    }
    if job.pipeline_route and stage == job.pipeline_route[0]:
        message["input_object_key"] = job.input_object_key

    return CommandEnvelope(
        queue=queue,
        message=message,
    )
