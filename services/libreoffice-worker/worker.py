#!/usr/bin/env python3
"""libreoffice-worker skeleton entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from ft_common.service import worker_main


if __name__ == "__main__":
    raise SystemExit(worker_main("libreoffice-worker", "docx_export"))
