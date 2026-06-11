#!/usr/bin/env bash
set -Eeuo pipefail

DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"

smoke_image() {
  service="$1"
  entrypoint="$2"
  image="${DOCKER_NAMESPACE}/file-translation-${service}:${IMAGE_TAG}"

  printf '[INFO] smoke image %s\n' "$image"
  docker run --rm "$image" python "$entrypoint" --smoke >/dev/null
  printf '[PASS] smoke image %s\n' "$image"
}

smoke_image job-service /app/service/app.py
smoke_image pdf2docx-worker /app/service/worker.py
smoke_image docx-extract-worker /app/service/worker.py
smoke_image translate-worker /app/service/worker.py
smoke_image docx-replace-worker /app/service/worker.py
smoke_image libreoffice-worker /app/service/worker.py
smoke_image pdf2hwpx-worker /app/service/worker.py
smoke_image hwpx-worker /app/service/worker.py
smoke_image email-worker /app/service/worker.py

printf '[PASS] all image smoke commands completed\n'
