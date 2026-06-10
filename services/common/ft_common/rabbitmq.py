"""Small RabbitMQ JSON helpers for worker command/event plumbing."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any, Callable

from ft_common.config import AppConfig


ConnectionFactory = Callable[["RabbitMQConnectionSettings"], Any]
JsonHandler = Callable[[dict[str, object]], None]


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


class RabbitMQJsonPublisher:
    def __init__(self, config: AppConfig, connection_factory: ConnectionFactory | None = None) -> None:
        self.settings = RabbitMQConnectionSettings.from_config(config)
        self.connection_factory = connection_factory or pika_blocking_connection

    def publish_json(self, queue: str, message: dict[str, object]) -> None:
        body = json.dumps(message, separators=(",", ":"), sort_keys=True).encode("utf-8")
        connection = self.connection_factory(self.settings)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=queue,
                body=body,
                properties=_delivery_properties(),
            )
        finally:
            _close_connection(connection)


class RabbitMQJsonConsumer:
    def __init__(
        self,
        config: AppConfig,
        connection_factory: ConnectionFactory | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = RabbitMQConnectionSettings.from_config(config)
        self.connection_factory = connection_factory or pika_blocking_connection
        self.logger = logger or logging.getLogger(config.service_name)

    def consume_forever(self, queue: str, handler: JsonHandler) -> None:
        connection = self.connection_factory(self.settings)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)

            def on_message(ch: Any, method: Any, properties: Any, body: bytes) -> None:
                try:
                    handler(decode_json_body(body))
                except Exception:
                    self.logger.exception("failed to handle RabbitMQ JSON message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue, on_message_callback=on_message)
            self.logger.info("consuming RabbitMQ queue=%s", queue)
            channel.start_consuming()
        finally:
            _close_connection(connection)


def decode_json_body(body: bytes) -> dict[str, object]:
    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("RabbitMQ body must decode to a JSON object")
    return decoded


def pika_blocking_connection(settings: RabbitMQConnectionSettings) -> Any:
    try:
        import pika  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("RabbitMQ mode requires the optional 'pika' package") from exc

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
