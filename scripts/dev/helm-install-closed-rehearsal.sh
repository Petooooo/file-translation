#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PATH="$HOME/.local/bin:$PATH"

RELEASE="${RELEASE:-file-translation-closed}"
NAMESPACE="${NAMESPACE:-file-translation-closed-rehearsal}"
DEPS_NAMESPACE="${DEPS_NAMESPACE:-file-translation-closed-rehearsal-deps}"
CHART_DIR="${CHART_DIR:-charts/file-translation}"
VALUES_FILE="${VALUES_FILE:-charts/file-translation/values.closed.local-rehearsal.yaml}"
SECRET_NAME="${SECRET_NAME:-file-translation-closed-rehearsal-secrets}"
CLUSTER_NAME="${CLUSTER_NAME:-file-translation-dev}"
DOCKER_NAMESPACE="${DOCKER_NAMESPACE:-petoo}"
IMAGE_TAG="${IMAGE_TAG:-0.1.0}"
TIMEOUT="${TIMEOUT:-10m}"

POSTGRES_SERVICE="${POSTGRES_SERVICE:-ft-closed-postgresql}"
RABBITMQ_SERVICE="${RABBITMQ_SERVICE:-ft-closed-rabbitmq}"
MINIO_SERVICE="${MINIO_SERVICE:-ft-closed-minio}"
POSTGRES_HOST="${POSTGRES_HOST:-${POSTGRES_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local}"
RABBITMQ_HOST="${RABBITMQ_HOST:-${RABBITMQ_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://${MINIO_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local:9000}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation-closed-rehearsal}"

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"

RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-file_translation}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-local-rehearsal-rabbitmq-password}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-file_translation}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-local-rehearsal-minio-secret-key}"
POSTGRES_USER="${POSTGRES_USER:-file_translation}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-local-rehearsal-postgres-password}"
TRANSLATION_API_TOKEN="${TRANSLATION_API_TOKEN:-local-rehearsal-translation-token}"
EMAIL_API_TOKEN="${EMAIL_API_TOKEN:-local-rehearsal-email-token}"
EMAIL_API_USERNAME="${EMAIL_API_USERNAME:-local-rehearsal-email-user}"
EMAIL_API_PASSWORD="${EMAIL_API_PASSWORD:-local-rehearsal-email-password}"

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

require_cmd() {
  has_cmd "$1" || die "$1 is required"
}

apply_runtime_secret() {
  namespace="$1"
  kubectl -n "$namespace" create secret generic "$SECRET_NAME" \
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
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
}

import_image_if_k3d() {
  image="$1"
  required="$2"

  if ! has_cmd k3d || ! k3d cluster list "$CLUSTER_NAME" >/dev/null 2>&1; then
    return
  fi
  if docker image inspect "$image" >/dev/null 2>&1; then
    k3d image import "$image" --cluster "$CLUSTER_NAME" >/dev/null
    note "Imported ${image}"
    return
  fi
  if [ "$required" = "required" ]; then
    die "Local image missing: ${image}; run scripts/dev/build-images.sh first"
  fi
  note "Optional image not present locally, cluster may pull it: ${image}"
}

require_cmd helm
require_cmd kubectl
require_cmd docker
docker info >/dev/null || die "Docker server is not reachable"
kubectl version --client >/dev/null || die "kubectl client is not available"

note "Ensuring namespaces exist"
kubectl create namespace "$DEPS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

note "Creating local rehearsal Secrets in dependency and app namespaces"
apply_runtime_secret "$DEPS_NAMESPACE"
apply_runtime_secret "$NAMESPACE"

note "Installing external dependency rehearsal stack in namespace ${DEPS_NAMESPACE}"
cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${POSTGRES_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: file-translation
    app.kubernetes.io/component: external-postgresql
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: external-postgresql
      app.kubernetes.io/part-of: file-translation-closed-rehearsal
  template:
    metadata:
      labels:
        app.kubernetes.io/component: external-postgresql
        app.kubernetes.io/part-of: file-translation-closed-rehearsal
    spec:
      containers:
        - name: postgresql
          image: ${POSTGRES_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: POSTGRES_DB
              value: file_translation
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: POSTGRES_USER
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: POSTGRES_PASSWORD
          ports:
            - name: postgres
              containerPort: 5432
          readinessProbe:
            exec:
              command: ["sh", "-c", "pg_isready -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\""]
            initialDelaySeconds: 5
            periodSeconds: 5
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ${POSTGRES_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: file-translation
    app.kubernetes.io/component: external-postgresql
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
spec:
  selector:
    app.kubernetes.io/component: external-postgresql
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
  ports:
    - name: postgres
      port: 5432
      targetPort: postgres
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${RABBITMQ_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: file-translation
    app.kubernetes.io/component: external-rabbitmq
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: external-rabbitmq
      app.kubernetes.io/part-of: file-translation-closed-rehearsal
  template:
    metadata:
      labels:
        app.kubernetes.io/component: external-rabbitmq
        app.kubernetes.io/part-of: file-translation-closed-rehearsal
    spec:
      containers:
        - name: rabbitmq
          image: ${RABBITMQ_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: RABBITMQ_DEFAULT_USER
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: RABBITMQ_USERNAME
            - name: RABBITMQ_DEFAULT_PASS
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: RABBITMQ_PASSWORD
            - name: RABBITMQ_DEFAULT_VHOST
              value: /
          ports:
            - name: amqp
              containerPort: 5672
            - name: management
              containerPort: 15672
          readinessProbe:
            exec:
              command: ["rabbitmq-diagnostics", "-q", "ping"]
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: data
              mountPath: /var/lib/rabbitmq
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ${RABBITMQ_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: file-translation
    app.kubernetes.io/component: external-rabbitmq
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
spec:
  selector:
    app.kubernetes.io/component: external-rabbitmq
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
  ports:
    - name: amqp
      port: 5672
      targetPort: amqp
    - name: management
      port: 15672
      targetPort: management
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${MINIO_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: file-translation
    app.kubernetes.io/component: external-minio
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: external-minio
      app.kubernetes.io/part-of: file-translation-closed-rehearsal
  template:
    metadata:
      labels:
        app.kubernetes.io/component: external-minio
        app.kubernetes.io/part-of: file-translation-closed-rehearsal
    spec:
      containers:
        - name: minio
          image: ${MINIO_IMAGE}
          imagePullPolicy: IfNotPresent
          args: ["server", "/data", "--console-address", ":9001"]
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: MINIO_ACCESS_KEY
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: MINIO_SECRET_KEY
          ports:
            - name: api
              containerPort: 9000
            - name: console
              containerPort: 9001
          readinessProbe:
            httpGet:
              path: /minio/health/ready
              port: api
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ${MINIO_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: file-translation
    app.kubernetes.io/component: external-minio
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
spec:
  selector:
    app.kubernetes.io/component: external-minio
    app.kubernetes.io/part-of: file-translation-closed-rehearsal
  ports:
    - name: api
      port: 9000
      targetPort: api
    - name: console
      port: 9001
      targetPort: console
EOF

note "Waiting for external dependency Deployments"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${POSTGRES_SERVICE}" --timeout="$TIMEOUT"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${RABBITMQ_SERVICE}" --timeout="$TIMEOUT"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${MINIO_SERVICE}" --timeout="$TIMEOUT"

note "Linting Helm chart"
helm lint "$CHART_DIR"

note "Rendering closed rehearsal Helm chart"
helm template "$RELEASE" "$CHART_DIR" -f "$VALUES_FILE" >/tmp/file-translation-helm-closed-rehearsal.yaml

if has_cmd k3d && k3d cluster list "$CLUSTER_NAME" >/dev/null 2>&1; then
  note "Importing local images into k3d cluster ${CLUSTER_NAME}"
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-job-service:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-pdf2docx-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-docx-extract-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-translate-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-docx-replace-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-libreoffice-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-pdf2hwpx-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-hwpx-worker:${IMAGE_TAG}" required
  import_image_if_k3d "${DOCKER_NAMESPACE}/file-translation-email-worker:${IMAGE_TAG}" required
  import_image_if_k3d "$POSTGRES_IMAGE" optional
  import_image_if_k3d "$RABBITMQ_IMAGE" optional
  import_image_if_k3d "$MINIO_IMAGE" optional
else
  note "k3d cluster ${CLUSTER_NAME} was not detected; relying on Kubernetes image pull policy"
fi

note "Installing/upgrading ${RELEASE} in namespace ${NAMESPACE}"
helm upgrade --install "$RELEASE" "$CHART_DIR" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  -f "$VALUES_FILE" \
  --set "app.namespace=${NAMESPACE}" \
  --set "secrets.existingSecret=${SECRET_NAME}" \
  --set "rabbitmq.host=${RABBITMQ_HOST}" \
  --set "postgresql.host=${POSTGRES_HOST}" \
  --set "minio.endpoint=${MINIO_ENDPOINT}" \
  --set "minio.bucket=${MINIO_BUCKET}" \
  --wait \
  --wait-for-jobs \
  --timeout "$TIMEOUT"

note "Waiting for queue and bucket init Jobs"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-queue-init" --timeout="$TIMEOUT"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-minio-init" --timeout="$TIMEOUT"

note "Waiting for file-translation Deployments"
kubectl -n "$NAMESPACE" rollout status deployment \
  -l "app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/part-of=file-translation" \
  --timeout="$TIMEOUT"

for bundled in "${RELEASE}-postgresql" "${RELEASE}-rabbitmq" "${RELEASE}-minio"; do
  if kubectl -n "$NAMESPACE" get deployment "$bundled" >/dev/null 2>&1; then
    die "Bundled dependency Deployment should be disabled but exists: ${bundled}"
  fi
done

pass "Closed-network local rehearsal install completed for ${RELEASE}"
