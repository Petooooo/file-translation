from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SERVICE_SMOKE_COMMANDS = [
    ("job-service", ROOT / "services" / "job-service" / "app.py", None),
    ("pdf2docx-worker", ROOT / "services" / "pdf2docx-worker" / "worker.py", "pdf2docx"),
    ("docx-extract-worker", ROOT / "services" / "docx-extract-worker" / "worker.py", "docx_extract"),
    ("translate-worker", ROOT / "services" / "translate-worker" / "worker.py", "docx_translate"),
    ("docx-replace-worker", ROOT / "services" / "docx-replace-worker" / "worker.py", "docx_replace"),
    ("libreoffice-worker", ROOT / "services" / "libreoffice-worker" / "worker.py", "docx_export"),
    ("pdf2hwpx-worker", ROOT / "services" / "pdf2hwpx-worker" / "worker.py", "pdf2hwpx"),
    ("hwpx-worker", ROOT / "services" / "hwpx-worker" / "worker.py", "hwpx_extract"),
    ("email-worker", ROOT / "services" / "email-worker" / "worker.py", "email_send"),
]


class ServiceSmokeTests(unittest.TestCase):
    def test_service_smoke_commands(self) -> None:
        for service_name, script, stage in SERVICE_SMOKE_COMMANDS:
            with self.subTest(service=service_name):
                result = subprocess.run(
                    [sys.executable, str(script), "--smoke"],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["service"], service_name)
                if stage is not None:
                    self.assertEqual(payload["stage"], stage)


if __name__ == "__main__":
    unittest.main()
