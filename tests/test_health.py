from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import threading
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))

from ft_common.config import load_config
from ft_common.health import make_handler


class HealthTests(unittest.TestCase):
    def test_health_endpoint_returns_json(self) -> None:
        config = load_config("job-service", "api", env={})
        server = ThreadingHTTPServer(("127.0.0.1", _free_port()), make_handler(config))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/healthz", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "job-service")
        self.assertEqual(payload["namespace"], "file-translation")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    unittest.main()
