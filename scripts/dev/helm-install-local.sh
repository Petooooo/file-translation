#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PATH="$HOME/.local/bin:$PATH"

RELEASE="${RELEASE:-file-translation}"
NAMESPACE="${NAMESPACE:-file-translation}"
CHART_DIR="${CHART_DIR:-charts/file-translation}"
VALUES_FILE="${VALUES_FILE:-charts/file-translation/values.local.yaml}"
CLUSTER_NAME="${CLUSTER_NAME:-file-translation-dev}"
DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"
TIMEOUT="${TIMEOUT:-10m}"

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

die() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

has_cmd helm || die "helm is required"
has_cmd kubectl || die "kubectl is required"
has_cmd docker || die "docker is required"

docker info >/dev/null || die "Docker server is not reachable"
kubectl version --client >/dev/null || die "kubectl client is not available"
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE" >/dev/null

note "Linting Helm chart"
helm lint "$CHART_DIR"

note "Rendering Helm chart"
helm template "$RELEASE" "$CHART_DIR" -f "$VALUES_FILE" >/tmp/file-translation-helm-local.yaml

images=(
  "${DOCKER_NAMESPACE}/file-translation-job-service:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-pdf2docx-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-docx-extract-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-translate-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-docx-replace-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-libreoffice-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-pdf2hwpx-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-hwpx-worker:${IMAGE_TAG}"
  "${DOCKER_NAMESPACE}/file-translation-email-worker:${IMAGE_TAG}"
)

if has_cmd k3d && k3d cluster list "$CLUSTER_NAME" >/dev/null 2>&1; then
  note "Importing local project images into k3d cluster ${CLUSTER_NAME}"
  for image in "${images[@]}"; do
    if docker image inspect "$image" >/dev/null 2>&1; then
      k3d image import "$image" --cluster "$CLUSTER_NAME" >/dev/null
      note "Imported ${image}"
    else
      die "Local image missing: ${image}; run scripts/dev/build-images.sh first"
    fi
  done
else
  note "k3d cluster ${CLUSTER_NAME} was not detected; relying on Kubernetes image pull policy"
fi

note "Installing/upgrading ${RELEASE} in namespace ${NAMESPACE}"
helm upgrade --install "$RELEASE" "$CHART_DIR" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  -f "$VALUES_FILE" \
  --wait \
  --wait-for-jobs \
  --timeout "$TIMEOUT"

note "Waiting for queue and bucket init Jobs"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-queue-init" --timeout="$TIMEOUT"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-minio-init" --timeout="$TIMEOUT"

note "Waiting for Deployments"
kubectl -n "$NAMESPACE" rollout status deployment \
  -l "app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/part-of=file-translation" \
  --timeout="$TIMEOUT"

pass "Helm local install completed for ${RELEASE}"
