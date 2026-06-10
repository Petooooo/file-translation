from __future__ import annotations

import unittest

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))

from ft_common.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_match_local_architecture(self) -> None:
        config = load_config("translate-worker", "worker", "docx_translate", env={})

        self.assertEqual(config.namespace, "file-translation")
        self.assertEqual(config.minio_bucket, "file-translation")
        self.assertEqual(config.rabbitmq_host, "rabbitmq")
        self.assertEqual(config.rabbitmq_username, "")
        self.assertEqual(config.rabbitmq_password, "")
        self.assertEqual(config.postgres_host, "postgresql")
        self.assertEqual(config.translation_provider, "mock")
        self.assertEqual(config.pdf2docx_image, "petoo/pdf2docx:0.5.13-py311-static")
        self.assertFalse(config.pdf2docx_enable_reports)
        self.assertEqual(config.job_service_command_publisher, "memory")
        self.assertEqual(config.job_service_event_consumer, "disabled")
        self.assertEqual(config.command_queues["docx_translate"], "q.commands.docx_translate")
        self.assertEqual(config.command_queues["hwpx_translate"], "q.commands.hwpx_translate")
        self.assertEqual(config.event_queues["stage_completed"], "q.events.stage_completed")

    def test_environment_overrides(self) -> None:
        config = load_config(
            "translate-worker",
            "worker",
            "docx_translate",
            env={
                "APP_ENV": "test",
                "NAMESPACE": "custom-ns",
                "RABBITMQ_HOST": "rabbitmq.custom",
                "RABBITMQ_PORT": "5673",
                "RABBITMQ_USERNAME": "rabbit-user",
                "RABBITMQ_PASSWORD": "rabbit-secret",
                "MINIO_BUCKET": "custom-bucket",
                "PDF2DOCX_IMAGE": "petoo/pdf2docx:test",
                "PDF2DOCX_ENABLE_REPORTS": "true",
                "JOB_SERVICE_COMMAND_PUBLISHER": "rabbitmq",
                "JOB_SERVICE_EVENT_CONSUMER": "rabbitmq",
                "QUEUE_COMMANDS_DOCX_TRANSLATE": "q.custom.docx_translate",
            },
        )

        self.assertEqual(config.app_env, "test")
        self.assertEqual(config.namespace, "custom-ns")
        self.assertEqual(config.rabbitmq_host, "rabbitmq.custom")
        self.assertEqual(config.rabbitmq_port, 5673)
        self.assertEqual(config.rabbitmq_username, "rabbit-user")
        self.assertEqual(config.rabbitmq_password, "rabbit-secret")
        self.assertEqual(config.minio_bucket, "custom-bucket")
        self.assertEqual(config.pdf2docx_image, "petoo/pdf2docx:test")
        self.assertTrue(config.pdf2docx_enable_reports)
        self.assertEqual(config.job_service_command_publisher, "rabbitmq")
        self.assertEqual(config.job_service_event_consumer, "rabbitmq")
        self.assertEqual(config.command_queues["docx_translate"], "q.custom.docx_translate")

    def test_invalid_integer_env_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            load_config("job-service", "api", env={"POSTGRES_PORT": "not-a-number"})

    def test_invalid_boolean_env_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            load_config("pdf2docx-worker", "worker", "pdf2docx", env={"PDF2DOCX_ENABLE_REPORTS": "maybe"})

    def test_safe_dict_excludes_secret_fields(self) -> None:
        config = load_config(
            "job-service",
            "api",
            env={
                "MINIO_SECRET_KEY": "do-not-show",
                "RABBITMQ_USERNAME": "do-not-show",
                "RABBITMQ_PASSWORD": "do-not-show",
                "POSTGRES_PASSWORD": "do-not-show",
            },
        )
        rendered = repr(config.safe_dict())

        self.assertNotIn("do-not-show", rendered)
        self.assertNotIn("PASSWORD", rendered)
        self.assertNotIn("SECRET", rendered)


if __name__ == "__main__":
    unittest.main()
