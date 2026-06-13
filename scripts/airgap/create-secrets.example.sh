#!/usr/bin/env bash
set -Eeuo pipefail

NAMESPACE="${NAMESPACE:-file-translation}"
SECRET_NAME="${SECRET_NAME:-file-translation-runtime-secrets}"

RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-<rabbitmq-username>}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-<rabbitmq-password>}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-<minio-access-key>}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-<minio-secret-key>}"
POSTGRES_USER="${POSTGRES_USER:-<postgres-user>}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-<postgres-password>}"
TRANSLATION_API_TOKEN="${TRANSLATION_API_TOKEN:-<translation-api-token>}"
EMAIL_API_TOKEN="${EMAIL_API_TOKEN:-<email-api-token>}"
EMAIL_API_USERNAME="${EMAIL_API_USERNAME:-<email-api-username>}"
EMAIL_API_PASSWORD="${EMAIL_API_PASSWORD:-<email-api-password>}"

die() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require_value() {
  name="$1"
  value="$2"
  case "$value" in
    ""|\<*\>)
      die "Set ${name} to the real deployment value before creating ${SECRET_NAME}"
      ;;
  esac
}

has_cmd kubectl || die "kubectl is required"

require_value RABBITMQ_USERNAME "$RABBITMQ_USERNAME"
require_value RABBITMQ_PASSWORD "$RABBITMQ_PASSWORD"
require_value MINIO_ACCESS_KEY "$MINIO_ACCESS_KEY"
require_value MINIO_SECRET_KEY "$MINIO_SECRET_KEY"
require_value POSTGRES_USER "$POSTGRES_USER"
require_value POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
require_value TRANSLATION_API_TOKEN "$TRANSLATION_API_TOKEN"
require_value EMAIL_API_TOKEN "$EMAIL_API_TOKEN"
require_value EMAIL_API_USERNAME "$EMAIL_API_USERNAME"
require_value EMAIL_API_PASSWORD "$EMAIL_API_PASSWORD"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
  --from-literal=RABBITMQ_USERNAME="$RABBITMQ_USERNAME" \
  --from-literal=RABBITMQ_PASSWORD="$RABBITMQ_PASSWORD" \
  --from-literal=MINIO_ACCESS_KEY="$MINIO_ACCESS_KEY" \
  --from-literal=MINIO_SECRET_KEY="$MINIO_SECRET_KEY" \
  --from-literal=POSTGRES_USER="$POSTGRES_USER" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=TRANSLATION_API_TOKEN="$TRANSLATION_API_TOKEN" \
  --from-literal=EMAIL_API_TOKEN="$EMAIL_API_TOKEN" \
  --from-literal=EMAIL_API_USERNAME="$EMAIL_API_USERNAME" \
  --from-literal=EMAIL_API_PASSWORD="$EMAIL_API_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

printf '[PASS] Created or updated Secret %s/%s\n' "$NAMESPACE" "$SECRET_NAME"
