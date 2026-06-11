#!/usr/bin/env bash
set -Eeuo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

run_smoke() {
  name="$1"
  script="$2"
  printf '[INFO] smoke %s\n' "$name"
  "$PYTHON_BIN" "$script" --smoke >/dev/null
  printf '[PASS] smoke %s\n' "$name"
}

run_smoke job-service services/job-service/app.py
run_smoke pdf2docx-worker services/pdf2docx-worker/worker.py
run_smoke docx-extract-worker services/docx-extract-worker/worker.py
run_smoke translate-worker services/translate-worker/worker.py
run_smoke docx-replace-worker services/docx-replace-worker/worker.py
run_smoke libreoffice-worker services/libreoffice-worker/worker.py
run_smoke pdf2hwpx-worker services/pdf2hwpx-worker/worker.py
run_smoke hwpx-worker services/hwpx-worker/worker.py
run_smoke email-worker services/email-worker/worker.py

printf '[PASS] all service smoke commands completed\n'
