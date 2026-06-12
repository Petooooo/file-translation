"""docx-extract-worker command-line entrypoint."""

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
from ft_common.worker_runtime import build_stage_command_handler
from docx_extract_worker.artifacts import (
    event_queue_key,
    process_docx_extract_command,
    stage_failed_event,
)
from docx_extract_worker.extraction import extract_text_units_from_docx, write_text_units_json


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="docx-extract-worker runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ docx_extract commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/docx-extract-worker")
    parser.add_argument("--extract-local", action="store_true", help="extract text units from a local DOCX")
    parser.add_argument("--input", dest="input_path", help="local input DOCX path for --extract-local")
    parser.add_argument("--output", dest="output_path", help="local text_units.json path for --extract-local")
    parser.add_argument("--job-id", default="local-docx-extract")
    parser.add_argument("--input-type", default="docx", choices=["pdf", "docx"])
    parser.add_argument("--source-lang", default="en")
    parser.add_argument("--target-lang", default="ko")
    args = parser.parse_args(argv)

    config = load_config("docx-extract-worker", "worker", "docx_extract")
    if args.smoke:
        print_smoke(config)
        return 0
    if args.extract_local:
        return _extract_local(args)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        store = MinioArtifactStore.from_config(config)
        publisher = RabbitMQJsonPublisher(config)
        consumer = RabbitMQJsonConsumer(config, logger=logger)
        command_queue = config.command_queues["docx_extract"]

        def process_command(message: dict[str, object]) -> dict[str, object]:
            return process_docx_extract_command(
                message,
                store=store,
                work_root=Path(args.work_dir),
            )

        handle_command = build_stage_command_handler(
            config=config,
            stage="docx_extract",
            logger=logger,
            process_command=process_command,
            stage_failed_event=stage_failed_event,
            publish_event=lambda event: publisher.publish_json(config.event_queues[event_queue_key(event)], event),
        )

        consumer.consume_forever(command_queue, handle_command)
        return 0

    logger.info("starting docx-extract-worker skeleton stage=docx_extract")
    logger.info("command queue=%s", config.command_queues["docx_extract"])

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
        logger.info("worker idle heartbeat stage=docx_extract")

    logger.info("worker stopped")
    return 0


def _extract_local(args: argparse.Namespace) -> int:
    if not args.input_path or not args.output_path:
        raise SystemExit("--extract-local requires --input and --output")

    payload = extract_text_units_from_docx(
        Path(args.input_path),
        job_id=args.job_id,
        input_type=args.input_type,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    )
    write_text_units_json(payload, Path(args.output_path))
    print(
        json.dumps(
            {
                "status": "extracted",
                "stage": "docx_extract",
                "units": len(payload["units"]),
                "output": args.output_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0
