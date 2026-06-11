"""docx-replace-worker command-line entrypoint."""

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
from docx_replace_worker.artifacts import event_queue_key, process_docx_replace_command, stage_failed_event
from docx_replace_worker.replacement import replace_docx_text_units


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="docx-replace-worker runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ docx_replace commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/docx-replace-worker")
    parser.add_argument("--replace-local", action="store_true", help="replace text in a local DOCX")
    parser.add_argument("--input-docx", dest="input_docx_path", help="local input DOCX path for --replace-local")
    parser.add_argument("--text-units", dest="text_units_path", help="local text_units.json path for --replace-local")
    parser.add_argument(
        "--translated-units",
        dest="translated_units_path",
        help="local translated_units.json path for --replace-local",
    )
    parser.add_argument("--output", dest="output_docx_path", help="local translated DOCX path for --replace-local")
    args = parser.parse_args(argv)

    config = load_config("docx-replace-worker", "worker", "docx_replace")
    if args.smoke:
        print_smoke(config)
        return 0
    if args.replace_local:
        return _replace_local(args)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        store = MinioArtifactStore.from_config(config)
        publisher = RabbitMQJsonPublisher(config)
        consumer = RabbitMQJsonConsumer(config, logger=logger)
        command_queue = config.command_queues["docx_replace"]

        def handle_command(message: dict[str, object]) -> None:
            try:
                event = process_docx_replace_command(
                    message,
                    store=store,
                    work_root=Path(args.work_dir),
                )
            except Exception as exc:
                logger.exception("docx_replace command failed")
                event = stage_failed_event(message, exc)
            publisher.publish_json(config.event_queues[event_queue_key(event)], event)

        consumer.consume_forever(command_queue, handle_command)
        return 0

    logger.info("starting docx-replace-worker skeleton stage=docx_replace")
    logger.info("command queue=%s", config.command_queues["docx_replace"])

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
        logger.info("worker idle heartbeat stage=docx_replace")

    logger.info("worker stopped")
    return 0


def _replace_local(args: argparse.Namespace) -> int:
    required_args = {
        "--input-docx": args.input_docx_path,
        "--text-units": args.text_units_path,
        "--translated-units": args.translated_units_path,
        "--output": args.output_docx_path,
    }
    missing = [name for name, value in required_args.items() if not value]
    if missing:
        raise SystemExit(f"--replace-local requires {', '.join(missing)}")

    result = replace_docx_text_units(
        input_docx_path=Path(args.input_docx_path),
        text_units_path=Path(args.text_units_path),
        translated_units_path=Path(args.translated_units_path),
        output_docx_path=Path(args.output_docx_path),
    )
    print(
        json.dumps(
            {
                "status": "replaced",
                "stage": "docx_replace",
                "replaced_units": result["replaced_units"],
                "output": args.output_docx_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0

