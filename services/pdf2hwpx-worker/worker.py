#!/usr/bin/env python3
"""pdf2hwpx-worker entrypoint wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from pdf2hwpx_worker.main import main


if __name__ == "__main__":
    raise SystemExit(main())
