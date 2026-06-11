"""RabbitMQ adapters for job-service command publish and event consume."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from ft_common.config import AppConfig
from job_service.orchestrator import JobService
from job_service.publisher import CommandEnvelope, CommandPublisher, build_command_envelope
from job_service.models import Job


ConnectionFactory = Callable[["RabbitMQConnectionSettings"], Any]


@dataclass(frozen=True)
class RabbitMQConnectionSettings:
    host: str
    port: int
    vhost: str
    username: str
    password: str

    @classmethod
    def from_config(cls, config: AppConfig) -> "RabbitMQConnectionSettings":
        return cls(
            host=config.rabbitmq_host,
            port=config.rabbitmq_port,
            vhost=config.rabbitmq_vhost,
            username=config.rabbitmq_username,
            password=config.rabbitmq_password,
        )


def event_queue_names(config: AppConfig) -> list[str]:
    return [
        config.event_queues["stage_completed"],
        config.event_queues["stage_failed"],
        config.event_queues["progress"],
    ]


def decode_event_body(body: bytes) -> dict[str, object]:
    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("RabbitMQ event body must decode to a JSON object")
    return decoded


class RabbitMQCommandPublisher(CommandPublisher):
    def __init__(
        self,
        config: AppConfig,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self.config = config
        self.settings = RabbitMQConnectionSettings.from_config(config)
        self.connection_factory = connection_factory or pika_blocking_connection

    def publish_command(self, job: Job, stage: str) -> CommandEnvelope:
        envelope = build_command_envelope(self.config, job, stage)
        body = json.dumps(envelope.message, separators=(",", ":"), sort_keys=True).encode("utf-8")
        connection = self.connection_factory(self.settings)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=envelope.queue, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=envelope.queue,
                body=body,
                properties=_delivery_properties(),
            )
        finally:
            _close_connection(connection)
        return envelope


class RabbitMQEventConsumer:
    def __init__(
        self,
        config: AppConfig,
        service: JobService,
        connection_factory: ConnectionFactory | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.service = service
        self.settings = RabbitMQConnectionSettings.from_config(config)
        self.connection_factory = connection_factory or pika_blocking_connection
        self.logger = logger or logging.getLogger(config.service_name)

    def consume_forever(self) -> None:
        connection = self.connection_factory(self.settings)
        try:
            channel = connection.channel()
            for queue in event_queue_names(self.config):
                channel.queue_declare(queue=queue, durable=True)
                channel.basic_consume(queue=queue, on_message_callback=self._on_message)
            self.logger.info("consuming RabbitMQ events from queues=%s", ",".join(event_queue_names(self.config)))
            channel.start_consuming()
        finally:
            _close_connection(connection)

    def _on_message(self, channel: Any, method: Any, properties: Any, body: bytes) -> None:
        try:
            event = decode_event_body(body)
            self.service.handle_event(event)
        except Exception:
            self.logger.exception("failed to handle RabbitMQ event")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        channel.basic_ack(delivery_tag=method.delivery_tag)


def pika_blocking_connection(settings: RabbitMQConnectionSettings) -> Any:
    try:
        import pika  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "RabbitMQ mode requires the optional 'pika' package. "
            "Install service requirements or use JOB_SERVICE_COMMAND_PUBLISHER=memory."
        ) from exc

    credentials = None
    if settings.username and settings.password:
        credentials = pika.PlainCredentials(settings.username, settings.password)

    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.host,
            port=settings.port,
            virtual_host=settings.vhost,
            credentials=credentials,
        )
    )


def _delivery_properties() -> Any:
    try:
        import pika  # type: ignore[import-not-found]
    except ImportError:
        return None
    return pika.BasicProperties(content_type="application/json", delivery_mode=2)


def _close_connection(connection: Any) -> None:
    close = getattr(connection, "close", None)
    if callable(close):
        close()
