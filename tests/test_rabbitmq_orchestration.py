from __future__ import annotations

from datetime import date
import json
import logging
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))
sys.path.insert(0, str(ROOT / "services" / "job-service"))

from ft_common.config import load_config
from job_service.main import build_command_publisher
from job_service.orchestrator import JobService
from job_service.publisher import InMemoryCommandPublisher
from job_service.rabbitmq import (
    RabbitMQCommandPublisher,
    RabbitMQEventConsumer,
    decode_event_body,
    event_queue_names,
)
from job_service.repository import InMemoryJobRepository


class FakeChannel:
    def __init__(self) -> None:
        self.declared: list[tuple[str, bool]] = []
        self.published: list[dict[str, object]] = []
        self.acks: list[int] = []
        self.nacks: list[tuple[int, bool]] = []
        self.consumers: list[tuple[str, object]] = []
        self.started = False

    def queue_declare(self, *, queue: str, durable: bool) -> None:
        self.declared.append((queue, durable))

    def basic_publish(self, *, exchange: str, routing_key: str, body: bytes, properties: object) -> None:
        self.published.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "body": body,
                "properties": properties,
            }
        )

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


class RabbitMQOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("job-service", "api", env={})
        self.logger = logging.getLogger("test-rabbitmq-consumer")
        self.logger.disabled = True

    def create_service(self) -> tuple[JobService, InMemoryCommandPublisher]:
        publisher = InMemoryCommandPublisher(self.config)
        service = JobService(InMemoryJobRepository(), publisher)
        return service, publisher

    def create_docx_job(self, service: JobService):
        return service.create_job(
            user_id="12345678",
            input_type="docx",
            source_lang="en",
            target_lang="ko",
            original_filename="sample.docx",
            file_id="a8f3k2p9",
            job_id="job-docx",
            today=date(2026, 1, 21),
        )

    def test_build_command_publisher_selects_configured_mode(self) -> None:
        memory_config = load_config("job-service", "api", env={})
        rabbit_config = load_config("job-service", "api", env={"JOB_SERVICE_COMMAND_PUBLISHER": "rabbitmq"})

        self.assertIsInstance(build_command_publisher(memory_config), InMemoryCommandPublisher)
        self.assertIsInstance(build_command_publisher(rabbit_config), RabbitMQCommandPublisher)

        invalid_config = load_config("job-service", "api", env={"JOB_SERVICE_COMMAND_PUBLISHER": "not-a-mode"})
        with self.assertRaises(ValueError):
            build_command_publisher(invalid_config)

    def test_event_queue_names_match_contract_order(self) -> None:
        self.assertEqual(
            event_queue_names(self.config),
            ["q.events.stage_completed", "q.events.stage_failed", "q.events.progress"],
        )

    def test_decode_event_body_requires_json_object(self) -> None:
        self.assertEqual(decode_event_body(b'{"event_type":"stage.completed"}'), {"event_type": "stage.completed"})
        with self.assertRaises(ValueError):
            decode_event_body(b'["not-an-object"]')

    def test_rabbitmq_command_publisher_declares_and_publishes_command(self) -> None:
        service, _ = self.create_service()
        job, _ = self.create_docx_job(service)
        fake_channel = FakeChannel()
        fake_connection = FakeConnection(fake_channel)

        publisher = RabbitMQCommandPublisher(self.config, connection_factory=lambda settings: fake_connection)
        envelope = publisher.publish_command(job, "docx_extract")

        self.assertEqual(envelope.queue, "q.commands.docx_extract")
        self.assertTrue(fake_connection.closed)
        self.assertEqual(fake_channel.declared, [("q.commands.docx_extract", True)])
        self.assertEqual(fake_channel.published[0]["exchange"], "")
        self.assertEqual(fake_channel.published[0]["routing_key"], "q.commands.docx_extract")
        body = json.loads(fake_channel.published[0]["body"].decode("utf-8"))
        self.assertEqual(body["job_id"], "job-docx")
        self.assertEqual(body["input_type"], "docx")
        self.assertEqual(body["stage"], "docx_extract")
        self.assertEqual(body["object_prefix"], "2026-01-21/12345678/a8f3k2p9")

    def test_rabbitmq_event_consumer_dispatches_event_and_acks(self) -> None:
        service, publisher = self.create_service()
        job, _ = self.create_docx_job(service)
        fake_channel = FakeChannel()
        consumer = RabbitMQEventConsumer(self.config, service, logger=self.logger)

        body = json.dumps(
            {
                "event_type": "stage.completed",
                "job_id": job.job_id,
                "input_type": "docx",
                "stage": "docx_extract",
            }
        ).encode("utf-8")
        consumer._on_message(fake_channel, FakeMethod(11), None, body)

        self.assertEqual(fake_channel.acks, [11])
        self.assertEqual(fake_channel.nacks, [])
        self.assertEqual(job.current_stage, "docx_translate")
        self.assertEqual(publisher.published[-1].queue, "q.commands.docx_translate")

    def test_rabbitmq_event_consumer_rejects_bad_event_without_requeue(self) -> None:
        service, _ = self.create_service()
        fake_channel = FakeChannel()
        consumer = RabbitMQEventConsumer(self.config, service, logger=self.logger)

        consumer._on_message(fake_channel, FakeMethod(12), None, b'["not-an-object"]')

        self.assertEqual(fake_channel.acks, [])
        self.assertEqual(fake_channel.nacks, [(12, False)])

    def test_consume_forever_declares_all_event_queues(self) -> None:
        service, _ = self.create_service()
        fake_channel = FakeChannel()
        fake_connection = FakeConnection(fake_channel)
        consumer = RabbitMQEventConsumer(
            self.config,
            service,
            connection_factory=lambda settings: fake_connection,
            logger=self.logger,
        )

        consumer.consume_forever()

        self.assertTrue(fake_connection.closed)
        self.assertTrue(fake_channel.started)
        self.assertEqual(
            fake_channel.declared,
            [
                ("q.events.stage_completed", True),
                ("q.events.stage_failed", True),
                ("q.events.progress", True),
            ],
        )
        self.assertEqual([queue for queue, _ in fake_channel.consumers], event_queue_names(self.config))


if __name__ == "__main__":
    unittest.main()
