#!/usr/bin/env python3
"""pdf2docx-worker skeleton entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from pdf2docx_worker.main import main


if __name__ == "__main__":
    raise SystemExit(main())
