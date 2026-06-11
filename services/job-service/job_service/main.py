"""job-service executable wiring."""

from __future__ import annotations

import argparse
import json
import threading
from typing import Sequence

from ft_common.config import AppConfig, load_config
from ft_common.health import health_payload
from ft_common.json_log import configure_logging
from job_service.api import serve_api
from job_service.orchestrator import JobService
from job_service.publisher import CommandPublisher, InMemoryCommandPublisher
from job_service.rabbitmq import RabbitMQCommandPublisher, RabbitMQEventConsumer
from job_service.repository import InMemoryJobRepository


def build_command_publisher(config: AppConfig) -> CommandPublisher:
    if config.job_service_command_publisher == "memory":
        return InMemoryCommandPublisher(config)
    if config.job_service_command_publisher == "rabbitmq":
        return RabbitMQCommandPublisher(config)
    raise ValueError("JOB_SERVICE_COMMAND_PUBLISHER must be either 'memory' or 'rabbitmq'")


def build_service() -> tuple[AppConfig, JobService]:
    config = load_config("job-service", "api")
    publisher = build_command_publisher(config)
    service = JobService(InMemoryJobRepository(), publisher)
    return config, service


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="job-service routing skeleton")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--smoke", action="store_true", help="print health payload and exit")
    args = parser.parse_args(argv)

    config, service = build_service()
    if args.smoke:
        print(json.dumps(health_payload(config), separators=(",", ":"), sort_keys=True))
        return 0

    logger = configure_logging(config.service_name, config.log_level)
    if config.job_service_event_consumer == "rabbitmq":
        consumer = RabbitMQEventConsumer(config, service, logger=logger)
        thread = threading.Thread(target=consumer.consume_forever, name="rabbitmq-event-consumer", daemon=True)
        thread.start()
        logger.info("started RabbitMQ event consumer thread")
    elif config.job_service_event_consumer != "disabled":
        raise ValueError("JOB_SERVICE_EVENT_CONSUMER must be either 'disabled' or 'rabbitmq'")

    logger.info("starting job-service routing API on %s:%s", args.host, args.port)
    serve_api(config, service, args.host, args.port)
    return 0
