"""pdf2docx-worker command-line entrypoint."""

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
from pdf2docx_worker.artifacts import event_queue_key, process_pdf2docx_command, stage_failed_event
from pdf2docx_worker.conversion import (
    Pdf2DocxConversionRequest,
    default_report_paths,
    run_static_anchored_conversion,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pdf2docx-worker static anchored runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ pdf2docx commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/pdf2docx-worker")
    parser.add_argument("--convert-local", action="store_true", help="convert local PDF paths without RabbitMQ/MinIO")
    parser.add_argument("--input", dest="input_path", help="local input PDF path for --convert-local")
    parser.add_argument("--output", dest="output_path", help="local output DOCX path for --convert-local")
    parser.add_argument("--with-report", action="store_true", help="write JSON and Markdown conversion reports")
    parser.add_argument("--report", dest="report_json_path", help="local JSON report path")
    parser.add_argument("--markdown-report", dest="report_markdown_path", help="local Markdown report path")
    parser.add_argument("--password", help="PDF password if required")
    parser.add_argument("--overwrite", action="store_true", help="overwrite output DOCX/report files")
    args = parser.parse_args(argv)

    config = load_config("pdf2docx-worker", "worker", "pdf2docx")
    if args.smoke:
        print_smoke(config)
        return 0
    if args.convert_local:
        return _convert_local(args, config.pdf2docx_enable_reports)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        store = MinioArtifactStore.from_config(config)
        publisher = RabbitMQJsonPublisher(config)
        consumer = RabbitMQJsonConsumer(config, logger=logger)
        command_queue = config.command_queues["pdf2docx"]

        def process_command(message: dict[str, object]) -> dict[str, object]:
            return process_pdf2docx_command(
                message,
                store=store,
                work_root=Path(args.work_dir),
                reports_enabled=config.pdf2docx_enable_reports,
            )

        handle_command = build_stage_command_handler(
            config=config,
            stage="pdf2docx",
            logger=logger,
            process_command=process_command,
            stage_failed_event=stage_failed_event,
            publish_event=lambda event: publisher.publish_json(config.event_queues[event_queue_key(event)], event),
        )

        consumer.consume_forever(command_queue, handle_command)
        return 0

    logger.info("starting pdf2docx-worker skeleton stage=pdf2docx")
    logger.info("command queue=%s", config.command_queues["pdf2docx"])
    logger.info("converter image=%s", config.pdf2docx_image)

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
        logger.info("worker idle heartbeat stage=pdf2docx")

    logger.info("worker stopped")
    return 0


def _convert_local(args: argparse.Namespace, reports_enabled_by_config: bool) -> int:
    if not args.input_path or not args.output_path:
        raise SystemExit("--convert-local requires --input and --output")

    output_path = Path(args.output_path)
    report_json_path = Path(args.report_json_path) if args.report_json_path else None
    report_markdown_path = Path(args.report_markdown_path) if args.report_markdown_path else None
    if args.with_report or reports_enabled_by_config:
        default_json, default_markdown = default_report_paths(output_path)
        report_json_path = report_json_path or default_json
        report_markdown_path = report_markdown_path or default_markdown

    result = run_static_anchored_conversion(
        Pdf2DocxConversionRequest(
            input_path=Path(args.input_path),
            output_path=output_path,
            overwrite=args.overwrite,
            report_json_path=report_json_path,
            report_markdown_path=report_markdown_path,
            password=args.password,
        )
    )
    print(
        json.dumps(
            {
                "status": "converted",
                "stage": "pdf2docx",
                "outputs": result.outputs(),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0
