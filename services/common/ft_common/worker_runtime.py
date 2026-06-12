"""Shared worker runtime helpers for stage claim and early RabbitMQ ack."""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable
from urllib import request
from urllib.parse import quote

from ft_common.config import AppConfig
from ft_common.rabbitmq import RabbitMQMessageAction

ProcessCommand = Callable[[dict[str, object]], dict[str, object]]
FailedEventFactory = Callable[[dict[str, object], Exception], dict[str, object]]
PublishEvent = Callable[[dict[str, object]], None]


class StageClaimClient:
    def claim_stage(
        self,
        *,
        job_id: str,
        stage: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        raise NotImplementedError

    def heartbeat_stage(
        self,
        *,
        job_id: str,
        stage: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        raise NotImplementedError


class HttpStageClaimClient(StageClaimClient):
    def __init__(self, *, base_url: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, config: AppConfig) -> "HttpStageClaimClient":
        return cls(base_url=config.job_service_url, timeout_seconds=config.email_api_timeout_seconds)

    def claim_stage(
        self,
        *,
        job_id: str,
        stage: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self._post(f"/jobs/{quote(job_id, safe='')}/stages/{quote(stage, safe='')}/claim", payload)

    def heartbeat_stage(
        self,
        *,
        job_id: str,
        stage: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self._post(f"/jobs/{quote(job_id, safe='')}/stages/{quote(stage, safe='')}/heartbeat", payload)

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("job-service stage safety response must be a JSON object")
        return decoded


def build_stage_command_handler(
    *,
    config: AppConfig,
    stage: str,
    logger: logging.Logger,
    process_command: ProcessCommand,
    stage_failed_event: FailedEventFactory,
    publish_event: PublishEvent,
    claim_client: StageClaimClient | None = None,
) -> Callable[[dict[str, object]], RabbitMQMessageAction]:
    client = claim_client or HttpStageClaimClient.from_config(config)
    worker_id = f"{config.service_name}:{stage}"

    def handler(message: dict[str, object]) -> RabbitMQMessageAction:
        command_id = _optional_str(message.get("command_id"))
        if not command_id:
            return RabbitMQMessageAction(
                ack_before_work=False,
                work=lambda: _process_and_publish(
                    message=message,
                    process_command=process_command,
                    stage_failed_event=stage_failed_event,
                    publish_event=publish_event,
                    claim=None,
                    logger=logger,
                ),
            )

        job_id = str(message["job_id"])
        command_stage = str(message.get("stage", stage))
        claim = client.claim_stage(
            job_id=job_id,
            stage=command_stage,
            payload={
                "command_id": command_id,
                "attempt": int(message.get("attempt", 1)),
                "worker_id": worker_id,
                "idempotency_key": _optional_str(message.get("idempotency_key")) or command_id,
                "lease_seconds": int(message.get("lease_seconds", config.stage_claim_lease_seconds)),
                "max_attempts": int(message.get("max_attempts", config.stage_claim_max_attempts)),
            },
        )
        if claim.get("should_process") is not True:
            logger.info(
                "stage command no-op job_id=%s stage=%s claim_status=%s",
                job_id,
                command_stage,
                claim.get("claim_status"),
            )
            return RabbitMQMessageAction(ack_before_work=True)

        claimed_message = dict(message)
        for key in ("claim_id", "command_id", "idempotency_key", "attempt", "max_attempts"):
            value = claim.get(key)
            if value is not None:
                claimed_message[key] = value

        return RabbitMQMessageAction(
            ack_before_work=True,
            work=lambda: _process_with_heartbeat(
                message=claimed_message,
                claim=claim,
                client=client,
                config=config,
                process_command=process_command,
                stage_failed_event=stage_failed_event,
                publish_event=publish_event,
                logger=logger,
            ),
        )

    return handler


def _process_with_heartbeat(
    *,
    message: dict[str, object],
    claim: dict[str, object],
    client: StageClaimClient,
    config: AppConfig,
    process_command: ProcessCommand,
    stage_failed_event: FailedEventFactory,
    publish_event: PublishEvent,
    logger: logging.Logger,
) -> None:
    stop = threading.Event()
    thread = threading.Thread(
        target=_heartbeat_loop,
        args=(stop, client, message, claim, config, logger),
        name=f"stage-heartbeat-{message.get('stage')}",
        daemon=True,
    )
    thread.start()
    try:
        _process_and_publish(
            message=message,
            process_command=process_command,
            stage_failed_event=stage_failed_event,
            publish_event=publish_event,
            claim=claim,
            logger=logger,
        )
    finally:
        stop.set()
        thread.join(timeout=1)


def _process_and_publish(
    *,
    message: dict[str, object],
    process_command: ProcessCommand,
    stage_failed_event: FailedEventFactory,
    publish_event: PublishEvent,
    claim: dict[str, object] | None,
    logger: logging.Logger,
) -> None:
    try:
        event = process_command(message)
    except Exception as exc:
        logger.exception("%s command failed", message.get("stage"))
        event = stage_failed_event(message, exc)
    _enrich_event(event, message, claim)
    publish_event(event)


def _heartbeat_loop(
    stop: threading.Event,
    client: StageClaimClient,
    message: dict[str, object],
    claim: dict[str, object],
    config: AppConfig,
    logger: logging.Logger,
) -> None:
    interval = max(1, config.stage_claim_heartbeat_interval_seconds)
    while not stop.wait(interval):
        try:
            client.heartbeat_stage(
                job_id=str(message["job_id"]),
                stage=str(message["stage"]),
                payload={
                    "claim_id": _optional_str(claim.get("claim_id")),
                    "progress": message.get("progress", claim.get("progress", 0)),
                    "lease_seconds": int(message.get("lease_seconds", config.stage_claim_lease_seconds)),
                },
            )
        except Exception:
            logger.exception("failed to heartbeat stage claim job_id=%s stage=%s", message.get("job_id"), message.get("stage"))


def _enrich_event(event: dict[str, object], message: dict[str, object], claim: dict[str, object] | None) -> None:
    source = dict(message)
    if claim:
        for key in ("claim_id", "command_id", "idempotency_key", "attempt", "max_attempts"):
            if claim.get(key) is not None:
                source[key] = claim[key]
    for key in ("claim_id", "command_id", "idempotency_key", "attempt"):
        if source.get(key) is not None:
            event.setdefault(key, source[key])


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
