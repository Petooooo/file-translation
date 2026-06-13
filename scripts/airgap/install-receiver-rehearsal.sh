#!/usr/bin/env bash
set -Eeuo pipefail

BUNDLE_PATH="${1:-.}"

RELEASE="${RELEASE:-file-translation-airgap}"
NAMESPACE="${NAMESPACE:-file-translation-airgap}"
DEPS_NAMESPACE="${DEPS_NAMESPACE:-file-translation-airgap-deps}"
SECRET_NAME="${SECRET_NAME:-file-translation-airgap-runtime-secrets}"
MINIO_BUCKET="${MINIO_BUCKET:-file-translation-airgap}"
TIMEOUT="${TIMEOUT:-10m}"

POSTGRES_SERVICE="${POSTGRES_SERVICE:-ft-airgap-postgresql}"
RABBITMQ_SERVICE="${RABBITMQ_SERVICE:-ft-airgap-rabbitmq}"
MINIO_SERVICE="${MINIO_SERVICE:-ft-airgap-minio}"
POSTGRES_HOST="${POSTGRES_HOST:-${POSTGRES_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local}"
RABBITMQ_HOST="${RABBITMQ_HOST:-${RABBITMQ_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://${MINIO_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local:9000}"

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"

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

require_value() {
  name="$1"
  value="$2"
  case "$value" in
    ""|\<*\>)
      die "Set ${name} before running receiver rehearsal"
      ;;
  esac
}

resolve_bundle_dir() {
  path="$1"
  if [ -d "$path" ]; then
    printf '%s\n' "$path"
    return
  fi
  die "Bundle path is not a directory: ${path}"
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

require_cmd helm
require_cmd kubectl

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

bundle_dir="$(resolve_bundle_dir "$BUNDLE_PATH")"
chart_package="$(find "$bundle_dir/chart" -maxdepth 1 -name 'file-translation-*.tgz' -type f | sort | head -n 1)"
[ -n "$chart_package" ] || die "No packaged chart found in ${bundle_dir}/chart"
values_file="$bundle_dir/values/values.closed.local-rehearsal.yaml"
[ -f "$values_file" ] || die "Receiver rehearsal values not found: ${values_file}"

note "Ensuring namespaces exist"
kubectl create namespace "$DEPS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

note "Creating receiver rehearsal Secrets"
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
    app.kubernetes.io/component: external-postgresql
    app.kubernetes.io/part-of: file-translation-airgap-rehearsal
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: external-postgresql
      app.kubernetes.io/part-of: file-translation-airgap-rehearsal
  template:
    metadata:
      labels:
        app.kubernetes.io/component: external-postgresql
        app.kubernetes.io/part-of: file-translation-airgap-rehearsal
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
spec:
  selector:
    app.kubernetes.io/component: external-postgresql
    app.kubernetes.io/part-of: file-translation-airgap-rehearsal
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
    app.kubernetes.io/component: external-rabbitmq
    app.kubernetes.io/part-of: file-translation-airgap-rehearsal
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: external-rabbitmq
      app.kubernetes.io/part-of: file-translation-airgap-rehearsal
  template:
    metadata:
      labels:
        app.kubernetes.io/component: external-rabbitmq
        app.kubernetes.io/part-of: file-translation-airgap-rehearsal
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
            timeoutSeconds: 5
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
spec:
  selector:
    app.kubernetes.io/component: external-rabbitmq
    app.kubernetes.io/part-of: file-translation-airgap-rehearsal
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
    app.kubernetes.io/component: external-minio
    app.kubernetes.io/part-of: file-translation-airgap-rehearsal
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: external-minio
      app.kubernetes.io/part-of: file-translation-airgap-rehearsal
  template:
    metadata:
      labels:
        app.kubernetes.io/component: external-minio
        app.kubernetes.io/part-of: file-translation-airgap-rehearsal
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
spec:
  selector:
    app.kubernetes.io/component: external-minio
    app.kubernetes.io/part-of: file-translation-airgap-rehearsal
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

note "Installing ${RELEASE} from bundled chart package"
helm upgrade --install "$RELEASE" "$chart_package" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  -f "$values_file" \
  --set "app.namespace=${NAMESPACE}" \
  --set "secrets.existingSecret=${SECRET_NAME}" \
  --set "rabbitmq.host=${RABBITMQ_HOST}" \
  --set "postgresql.host=${POSTGRES_HOST}" \
  --set "minio.endpoint=${MINIO_ENDPOINT}" \
  --set "minio.bucket=${MINIO_BUCKET}" \
  --wait \
  --wait-for-jobs \
  --timeout "$TIMEOUT"

kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-queue-init" --timeout="$TIMEOUT"
kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${RELEASE}-minio-init" --timeout="$TIMEOUT"
kubectl -n "$NAMESPACE" rollout status deployment \
  -l "app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/part-of=file-translation" \
  --timeout="$TIMEOUT"

pass "Receiver rehearsal install completed for ${RELEASE}"
