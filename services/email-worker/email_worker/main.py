"""email-worker command-line entrypoint."""

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
from email_worker.artifacts import (
    EmailSendCommand,
    EmailRequest,
    build_email_report,
    event_queue_key,
    process_email_send_command,
    stage_failed_event,
    write_email_report,
)
from email_worker.job_service_client import HttpJobServiceClient
from email_worker.provider import build_mail_provider


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="email-worker runtime")
    parser.add_argument("--smoke", action="store_true", help="print worker config and exit")
    parser.add_argument("--once", action="store_true", help="run a single no-op iteration and exit")
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--consume", action="store_true", help="consume RabbitMQ email_send commands")
    parser.add_argument("--work-dir", default="/tmp/file-translation/email-worker")
    parser.add_argument("--send-local", action="store_true", help="write a local mock email_report.json")
    parser.add_argument("--output", dest="output_report_path", help="local email_report.json path for --send-local")
    parser.add_argument("--job-id", default="local-email")
    parser.add_argument("--input-type", default="docx", choices=["pdf", "docx", "hwpx"])
    parser.add_argument("--object-prefix", default="2026-01-21/12345678/localemail")
    parser.add_argument("--to", default="user@example.local")
    parser.add_argument("--subject", default="Translated files are ready")
    parser.add_argument("--body", default="Translated files are ready.")
    parser.add_argument("--attachment", action="append", default=[], help="attachment object key for --send-local")
    args = parser.parse_args(argv)

    config = load_config("email-worker", "worker", "email_send")
    if args.smoke:
        print_smoke(config)
        return 0

    provider = build_mail_provider(config)
    if args.send_local:
        return _send_local(args, provider)

    logger = configure_logging(config.service_name, config.log_level)
    if args.consume:
        store = MinioArtifactStore.from_config(config)
        publisher = RabbitMQJsonPublisher(config)
        consumer = RabbitMQJsonConsumer(config, logger=logger)
        job_service_client = HttpJobServiceClient.from_config(config)
        command_queue = config.command_queues["email_send"]

        def process_command(message: dict[str, object]) -> dict[str, object]:
            return process_email_send_command(
                message,
                store=store,
                work_root=Path(args.work_dir),
                provider=provider,
                job_service_client=job_service_client,
                config=config,
            )

        handle_command = build_stage_command_handler(
            config=config,
            stage="email_send",
            logger=logger,
            process_command=process_command,
            stage_failed_event=stage_failed_event,
            publish_event=lambda event: publisher.publish_json(config.event_queues[event_queue_key(event)], event),
        )

        consumer.consume_forever(command_queue, handle_command)
        return 0

    logger.info("starting email-worker skeleton stage=email_send")
    logger.info("command queue=%s", config.command_queues["email_send"])
    logger.info("email provider=%s", provider.name)

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
        logger.info("worker idle heartbeat stage=email_send")

    logger.info("worker stopped")
    return 0


def _send_local(args: argparse.Namespace, provider: object) -> int:
    if not args.output_report_path:
        raise SystemExit("--send-local requires --output")
    attachments = args.attachment or [
        f"{args.object_prefix.strip('/')}/05_export/final.docx",
        f"{args.object_prefix.strip('/')}/05_export/final.pdf",
        f"{args.object_prefix.strip('/')}/06_hwpx/final.hwpx",
    ]
    request_payload = EmailRequest(
        uid=args.job_id,
        to=args.to,
        subject=args.subject,
        body=args.body,
        attachments=[{"object_key": attachment} for attachment in attachments],
        metadata={
            "job_id": args.job_id,
            "input_type": args.input_type,
            "object_prefix": args.object_prefix.strip("/"),
            "current_stage": "email_send",
        },
        input_type=args.input_type,
        object_prefix=args.object_prefix.strip("/"),
        report_object_key=f"{args.object_prefix.strip('/')}/reports/email_report.json",
    )
    result = provider.send_mail(
        uid=request_payload.uid,
        to=request_payload.to,
        subject=request_payload.subject,
        body=request_payload.body,
        attachments=request_payload.attachments,
        metadata=request_payload.metadata,
    )
    command = EmailSendCommand(job_id=args.job_id, stage="email_send", input_type=args.input_type)
    report = build_email_report(command=command, request_payload=request_payload, result=result)
    write_email_report(report, Path(args.output_report_path))
    print(
        json.dumps(
            {
                "status": "sent",
                "stage": "email_send",
                "provider": result.provider,
                "report": args.output_report_path,
                "attachments": len(request_payload.attachments),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0
