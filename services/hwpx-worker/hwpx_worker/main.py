"""hwpx-worker command-line entrypoint."""

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
from hwpx_worker.artifacts import (
    event_queue_key,
    process_hwpx_extract_command,
    process_hwpx_replace_command,
    stage_failed_event,
)
from hwpx_worker.hwpx_xml import create_sample_hwpx, extract_text_units_from_hwpx, replace_hwpx_text_units, write_text_units_json


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="hwpx-worker direct HWPX route runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume-extract", action="store_true", help="consume RabbitMQ hwpx_extract commands")
    parser.add_argument("--consume-replace", action="store_true", help="consume RabbitMQ hwpx_replace commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/hwpx-worker")
    parser.add_argument("--create-sample-local", action="store_true", help="create a local sample HWPX")
    parser.add_argument("--extract-local", action="store_true", help="extract local HWPX text units")
    parser.add_argument("--replace-local", action="store_true", help="replace local HWPX text units")
    parser.add_argument("--input", dest="input_hwpx_path", help="local HWPX input path")
    parser.add_argument("--output", dest="output_path", help="local output path")
    parser.add_argument("--text-units", dest="text_units_path", help="local text_units.json path")
    parser.add_argument("--translated-units", dest="translated_units_path", help="local translated_units.json path")
    parser.add_argument("--job-id", default="local-hwpx")
    parser.add_argument("--source-lang", default="und")
    parser.add_argument("--target-lang", default="und")
    parser.add_argument("--sample-text", action="append", default=[], help="sample text for --create-sample-local")
    args = parser.parse_args(argv)

    config_stage = "hwpx_replace" if args.consume_replace or args.replace_local else "hwpx_extract"
    config = load_config("hwpx-worker", "worker", config_stage)
    if args.smoke:
        print_smoke(config)
        return 0
    if args.create_sample_local:
        return _create_sample_local(args)
    if args.extract_local:
        return _extract_local(args)
    if args.replace_local:
        return _replace_local(args)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume_extract:
        _consume(config, args, logger, stage="hwpx_extract")
        return 0
    if args.consume_replace:
        _consume(config, args, logger, stage="hwpx_replace")
        return 0

    logger.info("starting hwpx-worker skeleton stage=%s", config_stage)
    logger.info("command queue=%s", config.command_queues[config_stage])

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
        logger.info("worker idle heartbeat stage=%s", config_stage)

    logger.info("worker stopped")
    return 0


def _consume(config: object, args: argparse.Namespace, logger: logging.Logger, *, stage: str) -> None:
    store = MinioArtifactStore.from_config(config)
    publisher = RabbitMQJsonPublisher(config)
    consumer = RabbitMQJsonConsumer(config, logger=logger)
    command_queue = config.command_queues[stage]
    processor = process_hwpx_replace_command if stage == "hwpx_replace" else process_hwpx_extract_command

    def handle_command(message: dict[str, object]) -> None:
        try:
            event = processor(
                message,
                store=store,
                work_root=Path(args.work_dir),
            )
        except Exception as exc:
            logger.exception("%s command failed", stage)
            event = stage_failed_event(message, exc)
        publisher.publish_json(config.event_queues[event_queue_key(event)], event)

    consumer.consume_forever(command_queue, handle_command)


def _create_sample_local(args: argparse.Namespace) -> int:
    if not args.output_path:
        raise SystemExit("--create-sample-local requires --output")
    texts = args.sample_text or ["Hello world", "Translate me"]
    create_sample_hwpx(Path(args.output_path), texts)
    print(
        json.dumps(
            {
                "status": "created",
                "stage": "hwpx_extract",
                "output": args.output_path,
                "units": len(texts),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


def _extract_local(args: argparse.Namespace) -> int:
    if not args.input_hwpx_path or not args.output_path:
        raise SystemExit("--extract-local requires --input and --output")
    payload = extract_text_units_from_hwpx(
        Path(args.input_hwpx_path),
        job_id=args.job_id,
        input_type="hwpx",
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    )
    write_text_units_json(payload, Path(args.output_path))
    print(
        json.dumps(
            {
                "status": "extracted",
                "stage": "hwpx_extract",
                "units": len(payload["units"]),
                "output": args.output_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


def _replace_local(args: argparse.Namespace) -> int:
    required_args = {
        "--input": args.input_hwpx_path,
        "--text-units": args.text_units_path,
        "--translated-units": args.translated_units_path,
        "--output": args.output_path,
    }
    missing = [name for name, value in required_args.items() if not value]
    if missing:
        raise SystemExit(f"--replace-local requires {', '.join(missing)}")
    result = replace_hwpx_text_units(
        input_hwpx_path=Path(args.input_hwpx_path),
        text_units_path=Path(args.text_units_path),
        translated_units_path=Path(args.translated_units_path),
        output_hwpx_path=Path(args.output_path),
    )
    print(
        json.dumps(
            {
                "status": "replaced",
                "stage": "hwpx_replace",
                "replaced_units": result["replaced_units"],
                "output": args.output_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0
