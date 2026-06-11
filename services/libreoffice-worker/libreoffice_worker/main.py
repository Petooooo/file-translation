"""libreoffice-worker command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Sequence

from ft_common.config import load_config
from ft_common.json_log import configure_logging
from ft_common.minio_store import MinioArtifactStore
from ft_common.rabbitmq import RabbitMQJsonConsumer, RabbitMQJsonPublisher
from ft_common.service import print_smoke
from libreoffice_worker.artifacts import (
    event_queue_key as export_event_queue_key,
    process_docx_export_command,
    stage_failed_event as export_stage_failed_event,
)
from libreoffice_worker.export import VALID_PDF_MODES, export_docx_artifacts
from libreoffice_worker.marker import mark_docx_spaces
from libreoffice_worker.marker_artifacts import (
    event_queue_key as marker_event_queue_key,
    process_docx_marker_command,
    stage_failed_event as marker_stage_failed_event,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="libreoffice-worker DOCX route runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ docx_export commands")
    parser.add_argument("--consume-marker", action="store_true", help="consume RabbitMQ docx_marker commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/libreoffice-worker")
    parser.add_argument("--export-local", action="store_true", help="export local DOCX artifacts")
    parser.add_argument("--mark-local", action="store_true", help="create a local marker DOCX")
    parser.add_argument("--input", dest="input_docx_path", help="local translated DOCX path for --export-local")
    parser.add_argument("--final-docx", dest="final_docx_path", help="local final DOCX path for --export-local")
    parser.add_argument("--final-pdf", dest="final_pdf_path", help="local final PDF path for --export-local")
    parser.add_argument("--marker-docx", dest="marker_docx_path", help="local marker DOCX path for --mark-local")
    parser.add_argument("--marker", help="marker character for --mark-local or --consume-marker")
    parser.add_argument("--pdf-mode", choices=sorted(VALID_PDF_MODES), help="PDF export mode")
    parser.add_argument("--libreoffice-binary", help="LibreOffice binary for --pdf-mode=libreoffice")
    args = parser.parse_args(argv)

    config_stage = "docx_marker" if args.consume_marker or args.mark_local else "docx_export"
    config = load_config("libreoffice-worker", "worker", config_stage)
    if args.smoke:
        print_smoke(config)
        return 0
    if args.export_local:
        return _export_local(args)
    if args.mark_local:
        return _mark_local(args)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        _consume_export(config, args, logger)
        return 0
    if args.consume_marker:
        _consume_marker(config, args, logger)
        return 0

    logger.info("starting libreoffice-worker skeleton stage=%s", config_stage)
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


def _consume_export(config: object, args: argparse.Namespace, logger: logging.Logger) -> None:
    store = MinioArtifactStore.from_config(config)
    publisher = RabbitMQJsonPublisher(config)
    consumer = RabbitMQJsonConsumer(config, logger=logger)
    command_queue = config.command_queues["docx_export"]
    pdf_mode = _pdf_mode(args)
    libreoffice_binary = _libreoffice_binary(args)

    def handle_command(message: dict[str, object]) -> None:
        try:
            event = process_docx_export_command(
                message,
                store=store,
                work_root=Path(args.work_dir),
                pdf_mode=pdf_mode,
                libreoffice_binary=libreoffice_binary,
            )
        except Exception as exc:
            logger.exception("docx_export command failed")
            event = export_stage_failed_event(message, exc)
        publisher.publish_json(config.event_queues[export_event_queue_key(event)], event)

    consumer.consume_forever(command_queue, handle_command)


def _consume_marker(config: object, args: argparse.Namespace, logger: logging.Logger) -> None:
    store = MinioArtifactStore.from_config(config)
    publisher = RabbitMQJsonPublisher(config)
    consumer = RabbitMQJsonConsumer(config, logger=logger)
    command_queue = config.command_queues["docx_marker"]
    marker = _marker(args)

    def handle_command(message: dict[str, object]) -> None:
        try:
            event = process_docx_marker_command(
                message,
                store=store,
                work_root=Path(args.work_dir),
                marker=marker,
            )
        except Exception as exc:
            logger.exception("docx_marker command failed")
            event = marker_stage_failed_event(message, exc)
        publisher.publish_json(config.event_queues[marker_event_queue_key(event)], event)

    consumer.consume_forever(command_queue, handle_command)


def _export_local(args: argparse.Namespace) -> int:
    required_args = {
        "--input": args.input_docx_path,
        "--final-docx": args.final_docx_path,
        "--final-pdf": args.final_pdf_path,
    }
    missing = [name for name, value in required_args.items() if not value]
    if missing:
        raise SystemExit(f"--export-local requires {', '.join(missing)}")

    result = export_docx_artifacts(
        input_docx_path=Path(args.input_docx_path),
        final_docx_path=Path(args.final_docx_path),
        final_pdf_path=Path(args.final_pdf_path),
        pdf_mode=_pdf_mode(args),
        libreoffice_binary=_libreoffice_binary(args),
    )
    print(
        json.dumps(
            {
                "status": "exported",
                "stage": "docx_export",
                "pdf_mode": result["pdf_mode"],
                "final_docx": args.final_docx_path,
                "final_pdf": args.final_pdf_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


def _mark_local(args: argparse.Namespace) -> int:
    required_args = {
        "--input": args.input_docx_path,
        "--marker-docx": args.marker_docx_path,
    }
    missing = [name for name, value in required_args.items() if not value]
    if missing:
        raise SystemExit(f"--mark-local requires {', '.join(missing)}")

    result = mark_docx_spaces(
        input_docx_path=Path(args.input_docx_path),
        marker_docx_path=Path(args.marker_docx_path),
        marker=_marker(args),
    )
    print(
        json.dumps(
            {
                "status": "marked",
                "stage": "docx_marker",
                "marked_text_nodes": result.marked_text_nodes,
                "replaced_spaces": result.replaced_spaces,
                "marker_docx": args.marker_docx_path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


def _pdf_mode(args: argparse.Namespace) -> str:
    return args.pdf_mode or os.environ.get("DOCX_EXPORT_PDF_MODE", "placeholder")


def _libreoffice_binary(args: argparse.Namespace) -> str:
    return args.libreoffice_binary or os.environ.get("LIBREOFFICE_BINARY", "soffice")


def _marker(args: argparse.Namespace) -> str:
    return args.marker or os.environ.get("DOCX_MARKER_TOKEN", "¡")
