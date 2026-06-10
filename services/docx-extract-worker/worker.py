#!/usr/bin/env python3
"""docx-extract-worker entrypoint wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from docx_extract_worker.main import main


if __name__ == "__main__":
    raise SystemExit(main())
