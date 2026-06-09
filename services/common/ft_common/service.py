"""Common entrypoint helpers for service skeletons."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from typing import Sequence

from ft_common.config import AppConfig, load_config
from ft_common.health import health_payload
from ft_common.json_log import configure_logging


def smoke_payload(config: AppConfig) -> dict[str, object]:
    return {
        "status": "ok",
        "service": config.service_name,
        "service_kind": config.service_kind,
        "stage": config.stage,
        "config": config.safe_dict(),
    }


def print_smoke(config: AppConfig) -> None:
    print(json.dumps(smoke_payload(config), separators=(",", ":"), sort_keys=True))


def job_service_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="job-service skeleton")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--smoke", action="store_true", help="print health payload and exit")
    args = parser.parse_args(argv)

    config = load_config("job-service", "api")
    if args.smoke:
        print(json.dumps(health_payload(config), separators=(",", ":"), sort_keys=True))
        return 0

    logger = configure_logging(config.service_name, config.log_level)
    logger.info("starting job-service health server on %s:%s", args.host, args.port)

    from ft_common.health import serve_health

    serve_health(config, args.host, args.port)
    return 0


def worker_main(service_name: str, stage: str, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{service_name} skeleton")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)

    config = load_config(service_name, "worker", stage)
    if args.smoke:
        print_smoke(config)
        return 0

    logger = configure_logging(config.service_name, config.log_level)
    logger.info("starting worker skeleton for stage=%s", stage)
    logger.info("command queue=%s", config.command_queues[stage])

    if args.once:
        logger.info("completed single no-op worker iteration")
        return 0

    stop = {"requested": False}

    def request_stop(signum: int, frame: object) -> None:
        stop["requested"] = True
        logging.getLogger(config.service_name).info("received signal=%s; stopping", signum)

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    while not stop["requested"]:
        time.sleep(args.idle_seconds)
        logger.info("worker idle heartbeat stage=%s", stage)

    logger.info("worker stopped")
    return 0
