"""pdf2hwpx-worker command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from pathlib import Path
from typing import Sequence

from ft_common.config import load_config
from ft_common.json_log import configure_logging
from ft_common.minio_store import MinioArtifactStore
from ft_common.rabbitmq import RabbitMQJsonConsumer, RabbitMQJsonPublisher
from ft_common.service import print_smoke
from pdf2hwpx_worker.artifacts import event_queue_key, process_pdf2hwpx_command, stage_failed_event
from pdf2hwpx_worker.placeholder import generate_placeholder_hwpx


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pdf2hwpx-worker runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ pdf2hwpx commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/pdf2hwpx-worker")
    parser.add_argument("--generate-local", action="store_true", help="generate placeholder HWPX from a marker DOCX")
    parser.add_argument("--input", dest="input_docx_path", help="local marker DOCX path for --generate-local")
    parser.add_argument("--output", dest="output_hwpx_path", help="local final HWPX path for --generate-local")
    parser.add_argument("--job-id", default="local-pdf2hwpx")
    parser.add_argument("--input-type", default="docx", choices=["pdf", "docx"])
    parser.add_argument("--object-prefix", default="2026-01-21/12345678/localpdf2hwpx")
    args = parser.parse_args(argv)

    config = load_config("pdf2hwpx-worker", "worker", "pdf2hwpx")
    if args.smoke:
        print_smoke(config)
        return 0
    if args.generate_local:
        return _generate_local(args)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        store = MinioArtifactStore.from_config(config)
        publisher = RabbitMQJsonPublisher(config)
        consumer = RabbitMQJsonConsumer(config, logger=logger)
        command_queue = config.command_queues["pdf2hwpx"]

        def handle_command(message: dict[str, object]) -> None:
            try:
                event = process_pdf2hwpx_command(
                    message,
                    store=store,
                    work_root=Path(args.work_dir),
                )
            except Exception as exc:
                logger.exception("pdf2hwpx command failed")
                event = stage_failed_event(message, exc)
            publisher.publish_json(config.event_queues[event_queue_key(event)], event)

        consumer.consume_forever(command_queue, handle_command)
        return 0

    logger.info("starting pdf2hwpx-worker skeleton stage=pdf2hwpx")
    logger.info("command queue=%s", config.command_queues["pdf2hwpx"])

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
        logger.info("worker idle heartbeat stage=pdf2hwpx")

    logger.info("worker stopped")
    return 0


def _generate_local(args: argparse.Namespace) -> int:
    required_args = {
        "--input": args.input_docx_path,
        "--output": args.output_hwpx_path,
    }
    missing = [name for name, value in required_args.items() if not value]
    if missing:
        raise SystemExit(f"--generate-local requires {', '.join(missing)}")

    result = generate_placeholder_hwpx(
        marker_docx_path=Path(args.input_docx_path),
        output_hwpx_path=Path(args.output_hwpx_path),
        job_id=args.job_id,
        input_type=args.input_type,
        object_prefix=args.object_prefix.strip("/"),
    )
    print(
        json.dumps(
            {
                "status": "generated",
                "stage": "pdf2hwpx",
                "provider": "placeholder",
                "output": args.output_hwpx_path,
                "source_docx_sha256": result.source_docx_sha256,
                "source_docx_size": result.source_docx_size,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0
