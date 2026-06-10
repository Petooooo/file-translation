"""job-service executable wiring."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from ft_common.config import load_config
from ft_common.health import health_payload
from ft_common.json_log import configure_logging
from job_service.api import serve_api
from job_service.orchestrator import JobService
from job_service.publisher import InMemoryCommandPublisher
from job_service.repository import InMemoryJobRepository


def build_service() -> tuple[object, JobService]:
    config = load_config("job-service", "api")
    publisher = InMemoryCommandPublisher(config)
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
    logger.info("starting job-service routing API on %s:%s", args.host, args.port)
    serve_api(config, service, args.host, args.port)
    return 0
