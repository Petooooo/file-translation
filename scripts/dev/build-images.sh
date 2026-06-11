#!/usr/bin/env bash
set -Eeuo pipefail

DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"

build_image() {
  service="$1"
  dockerfile="services/${service}/Dockerfile"
  image="${DOCKER_NAMESPACE}/file-translation-${service}:${IMAGE_TAG}"

  printf '[INFO] build %s\n' "$image"
  docker build -t "$image" -f "$dockerfile" .
  printf '[PASS] build %s\n' "$image"
}

build_image job-service
build_image pdf2docx-worker
build_image docx-extract-worker
build_image translate-worker
build_image docx-replace-worker
build_image libreoffice-worker
build_image pdf2hwpx-worker
build_image hwpx-worker
build_image email-worker

printf '[PASS] all images built with tag %s\n' "$IMAGE_TAG"
