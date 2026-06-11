#!/usr/bin/env bash
set -Eeuo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
WORK_DIR="${WORK_DIR:-$(mktemp -d)}"

mkdir -p "$WORK_DIR"

"$PYTHON_BIN" services/hwpx-worker/worker.py \
  --create-sample-local \
  --output "$WORK_DIR/input.hwpx" \
  --sample-text "Hello world" \
  --sample-text "Translate me" >/dev/null

"$PYTHON_BIN" services/hwpx-worker/worker.py \
  --extract-local \
  --input "$WORK_DIR/input.hwpx" \
  --output "$WORK_DIR/text_units.json" \
  --source-lang en \
  --target-lang ko >/dev/null

"$PYTHON_BIN" services/translate-worker/worker.py \
  --translate-local \
  --input "$WORK_DIR/text_units.json" \
  --output "$WORK_DIR/translated_units.json" \
  --source-lang en \
  --target-lang ko >/dev/null

"$PYTHON_BIN" services/hwpx-worker/worker.py \
  --replace-local \
  --input "$WORK_DIR/input.hwpx" \
  --text-units "$WORK_DIR/text_units.json" \
  --translated-units "$WORK_DIR/translated_units.json" \
  --output "$WORK_DIR/translated.hwpx" >/dev/null

"$PYTHON_BIN" services/libreoffice-worker/worker.py \
  --export-hwpx-local \
  --input-hwpx "$WORK_DIR/translated.hwpx" \
  --final-hwpx "$WORK_DIR/final.hwpx" \
  --final-docx "$WORK_DIR/final.docx" \
  --final-pdf "$WORK_DIR/final.pdf" >/dev/null

"$PYTHON_BIN" - "$WORK_DIR" <<'PY'
from pathlib import Path
import sys
import zipfile

work_dir = Path(sys.argv[1])
required = [
    work_dir / "input.hwpx",
    work_dir / "text_units.json",
    work_dir / "translated_units.json",
    work_dir / "translated.hwpx",
    work_dir / "final.hwpx",
    work_dir / "final.docx",
    work_dir / "final.pdf",
]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"missing expected files: {missing}")
if not (work_dir / "final.pdf").read_bytes().startswith(b"%PDF-1.4"):
    raise SystemExit("final.pdf is not a placeholder PDF")
with zipfile.ZipFile(work_dir / "final.docx", "r") as archive:
    if "word/document.xml" not in archive.namelist():
        raise SystemExit("final.docx does not contain word/document.xml")
with zipfile.ZipFile(work_dir / "final.hwpx", "r") as archive:
    if "Contents/section0.xml" not in archive.namelist():
        raise SystemExit("final.hwpx does not contain Contents/section0.xml")
PY

printf '[PASS] HWPX local smoke completed in %s\n' "$WORK_DIR"
