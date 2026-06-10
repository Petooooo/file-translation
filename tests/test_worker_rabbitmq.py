from __future__ import annotations

from pathlib import Path
import json
import logging
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))

from ft_common.config import load_config
from ft_common.rabbitmq import RabbitMQJsonConsumer, RabbitMQJsonPublisher, decode_json_body


class FakeChannel:
    def __init__(self) -> None:
        self.declared: list[tuple[str, bool]] = []
        self.published: list[dict[str, object]] = []
        self.consumers: list[tuple[str, object]] = []
        self.acks: list[int] = []
        self.nacks: list[tuple[int, bool]] = []
        self.started = False

    def queue_declare(self, *, queue: str, durable: bool) -> None:
        self.declared.append((queue, durable))

    def basic_publish(self, *, exchange: str, routing_key: str, body: bytes, properties: object) -> None:
        self.published.append({"exchange": exchange, "routing_key": routing_key, "body": body, "properties": properties})

    def basic_consume(self, *, queue: str, on_message_callback: object) -> None:
        self.consumers.append((queue, on_message_callback))

    def start_consuming(self) -> None:
        self.started = True

    def basic_ack(self, *, delivery_tag: int) -> None:
        self.acks.append(delivery_tag)

    def basic_nack(self, *, delivery_tag: int, requeue: bool) -> None:
        self.nacks.append((delivery_tag, requeue))


class FakeConnection:
    def __init__(self, channel: FakeChannel) -> None:
        self._channel = channel
        self.closed = False

    def channel(self) -> FakeChannel:
        return self._channel

    def close(self) -> None:
        self.closed = True


class FakeMethod:
    def __init__(self, delivery_tag: int) -> None:
        self.delivery_tag = delivery_tag


class WorkerRabbitMQTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("pdf2docx-worker", "worker", "pdf2docx", env={})
        self.logger = logging.getLogger("test-worker-rabbitmq")
        self.logger.disabled = True

    def test_decode_json_body_requires_object(self) -> None:
        self.assertEqual(decode_json_body(b'{"job_id":"job-1"}'), {"job_id": "job-1"})
        with self.assertRaises(ValueError):
            decode_json_body(b'["bad"]')

    def test_publisher_declares_queue_and_publishes_json(self) -> None:
        fake_channel = FakeChannel()
        fake_connection = FakeConnection(fake_channel)
        publisher = RabbitMQJsonPublisher(self.config, connection_factory=lambda settings: fake_connection)

        publisher.publish_json("q.events.stage_completed", {"event_type": "stage.completed", "job_id": "job-1"})

        self.assertTrue(fake_connection.closed)
        self.assertEqual(fake_channel.declared, [("q.events.stage_completed", True)])
        self.assertEqual(fake_channel.published[0]["routing_key"], "q.events.stage_completed")
        self.assertEqual(json.loads(fake_channel.published[0]["body"].decode("utf-8"))["job_id"], "job-1")

    def test_consumer_acks_valid_message(self) -> None:
        fake_channel = FakeChannel()
        fake_connection = FakeConnection(fake_channel)
        seen: list[dict[str, object]] = []
        consumer = RabbitMQJsonConsumer(
            self.config,
            connection_factory=lambda settings: fake_connection,
            logger=self.logger,
        )

        consumer.consume_forever("q.commands.pdf2docx", seen.append)
        callback = fake_channel.consumers[0][1]
        callback(fake_channel, FakeMethod(7), None, b'{"job_id":"job-1"}')

        self.assertTrue(fake_channel.started)
        self.assertEqual(seen, [{"job_id": "job-1"}])
        self.assertEqual(fake_channel.acks, [7])
        self.assertEqual(fake_channel.nacks, [])

    def test_consumer_nacks_invalid_message_without_requeue(self) -> None:
        fake_channel = FakeChannel()
        fake_connection = FakeConnection(fake_channel)
        consumer = RabbitMQJsonConsumer(
            self.config,
            connection_factory=lambda settings: fake_connection,
            logger=self.logger,
        )

        consumer.consume_forever("q.commands.pdf2docx", lambda message: None)
        callback = fake_channel.consumers[0][1]
        callback(fake_channel, FakeMethod(8), None, b'["bad"]')

        self.assertEqual(fake_channel.acks, [])
        self.assertEqual(fake_channel.nacks, [(8, False)])


if __name__ == "__main__":
    unittest.main()
