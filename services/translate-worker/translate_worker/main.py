"""translate-worker command-line entrypoint."""

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
from translate_worker.artifacts import event_queue_key, process_translate_command, stage_failed_event
from translate_worker.provider import build_translation_provider
from translate_worker.translation import read_text_units_json, translate_text_units, write_translated_units_json


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="translate-worker runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ docx_translate commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/translate-worker")
    parser.add_argument("--translate-local", action="store_true", help="translate a local text_units.json file")
    parser.add_argument("--input", dest="input_path", help="local text_units.json path for --translate-local")
    parser.add_argument("--output", dest="output_path", help="local translated_units.json path for --translate-local")
    parser.add_argument("--source-lang", default=None)
    parser.add_argument("--target-lang", default=None)
    args = parser.parse_args(argv)

    config = load_config("translate-worker", "worker", "docx_translate")
    if args.smoke:
        print_smoke(config)
        return 0
    provider = build_translation_provider(config)
    if args.translate_local:
        return _translate_local(args, provider)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        store = MinioArtifactStore.from_config(config)
        publisher = RabbitMQJsonPublisher(config)
        consumer = RabbitMQJsonConsumer(config, logger=logger)
        command_queue = config.command_queues["docx_translate"]

        def handle_command(message: dict[str, object]) -> None:
            try:
                event = process_translate_command(
                    message,
                    store=store,
                    work_root=Path(args.work_dir),
                    provider=provider,
                    progress_publisher=lambda progress: publisher.publish_json(
                        config.event_queues[event_queue_key(progress)],
                        progress,
                    ),
                )
            except Exception as exc:
                logger.exception("docx_translate command failed")
                event = stage_failed_event(message, exc)
            publisher.publish_json(config.event_queues[event_queue_key(event)], event)

        consumer.consume_forever(command_queue, handle_command)
        return 0

    logger.info("starting translate-worker skeleton stage=docx_translate")
    logger.info("command queue=%s", config.command_queues["docx_translate"])
    logger.info("translation provider=%s", provider.name)

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
        logger.info("worker idle heartbeat stage=docx_translate")

    logger.info("worker stopped")
    return 0


def _translate_local(args: argparse.Namespace, provider: object) -> int:
    if not args.input_path or not args.output_path:
        raise SystemExit("--translate-local requires --input and --output")

    payload = read_text_units_json(Path(args.input_path))
    translated = translate_text_units(
        payload,
        provider=provider,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    )
    write_translated_units_json(translated, Path(args.output_path))
    print(
        json.dumps(
            {
                "status": "translated",
                "stage": "docx_translate",
                "provider": translated["provider"],
                "units": len(translated["units"]),
                "output": args.output_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0

