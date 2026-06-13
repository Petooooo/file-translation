#!/usr/bin/env bash
set -Eeuo pipefail

PATH="$HOME/.local/bin:$PATH"

CLUSTER_NAME="${CLUSTER_NAME:-file-translation-manual-airgap}"
KUBE_CONTEXT="${KUBE_CONTEXT:-k3d-${CLUSTER_NAME}}"
DEPS_NAMESPACE="${DEPS_NAMESPACE:-file-translation-deps}"
APP_NAMESPACE="${APP_NAMESPACE:-file-translation}"
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
TIMEOUT="${TIMEOUT:-10m}"

POSTGRES_SERVICE="${POSTGRES_SERVICE:-manual-postgresql}"
RABBITMQ_SERVICE="${RABBITMQ_SERVICE:-manual-rabbitmq}"
MINIO_SERVICE="${MINIO_SERVICE:-manual-minio}"
PGADMIN_SERVICE="${PGADMIN_SERVICE:-manual-pgadmin}"

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:3.13-management}"
MINIO_IMAGE="${MINIO_IMAGE:-minio/minio:RELEASE.2025-02-07T23-21-09Z}"
LOCAL_DEP_IMAGE_PULL_POLICY="${LOCAL_DEP_IMAGE_PULL_POLICY:-Never}"

ALLOW_ONLINE_INFRA_PULL="${ALLOW_ONLINE_INFRA_PULL:-}"
PGADMIN_IMAGE="${PGADMIN_IMAGE:-dpage/pgadmin4:latest}"
PGADMIN_IMAGE_PULL_POLICY="${PGADMIN_IMAGE_PULL_POLICY:-IfNotPresent}"
PGADMIN_DEFAULT_EMAIL="${PGADMIN_DEFAULT_EMAIL:-admin@example.local}"
PGADMIN_DEFAULT_PASSWORD="${PGADMIN_DEFAULT_PASSWORD:-change-me-local-only}"
ARGOCD_VERSION="${ARGOCD_VERSION:-v3.4.1}"
ARGOCD_INSTALL_URL="${ARGOCD_INSTALL_URL:-https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml}"

POSTGRES_DB="${POSTGRES_DB:-file_translation}"
POSTGRES_USER="${POSTGRES_USER:-file_translation}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-change-me-local-only}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-file_translation}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-change-me-local-only}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-file_translation}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-change-me-local-only}"

note() {
  printf '[INFO] %s\n' "$1"
}

pass() {
  printf '[PASS] %s\n' "$1"
}

warn() {
  printf '[WARN] %s\n' "$1" >&2
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

require_cmd kubectl

current_context="$(kubectl config current-context 2>/dev/null || true)"
if [ "$current_context" != "$KUBE_CONTEXT" ]; then
  note "Switching kubectl context to ${KUBE_CONTEXT}"
  kubectl config use-context "$KUBE_CONTEXT" >/dev/null
fi

note "Ensuring namespaces exist"
kubectl create namespace "$DEPS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create namespace "$APP_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create namespace "$ARGOCD_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

note "Creating local-only dependency Secrets"
kubectl -n "$DEPS_NAMESPACE" create secret generic manual-deps-secrets \
  --from-literal=POSTGRES_DB="$POSTGRES_DB" \
  --from-literal=POSTGRES_USER="$POSTGRES_USER" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=RABBITMQ_USERNAME="$RABBITMQ_USERNAME" \
  --from-literal=RABBITMQ_PASSWORD="$RABBITMQ_PASSWORD" \
  --from-literal=MINIO_ACCESS_KEY="$MINIO_ACCESS_KEY" \
  --from-literal=MINIO_SECRET_KEY="$MINIO_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

note "Installing manual PostgreSQL/RabbitMQ/MinIO dependencies"
cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${POSTGRES_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: ${POSTGRES_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${POSTGRES_SERVICE}
      app.kubernetes.io/part-of: file-translation-manual-airgap
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${POSTGRES_SERVICE}
        app.kubernetes.io/part-of: file-translation-manual-airgap
    spec:
      containers:
        - name: postgresql
          image: ${POSTGRES_IMAGE}
          imagePullPolicy: ${LOCAL_DEP_IMAGE_PULL_POLICY}
          env:
            - name: POSTGRES_DB
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
                  key: POSTGRES_DB
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
                  key: POSTGRES_USER
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
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
    app.kubernetes.io/name: ${POSTGRES_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
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
    app.kubernetes.io/name: ${RABBITMQ_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${RABBITMQ_SERVICE}
      app.kubernetes.io/part-of: file-translation-manual-airgap
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${RABBITMQ_SERVICE}
        app.kubernetes.io/part-of: file-translation-manual-airgap
    spec:
      containers:
        - name: rabbitmq
          image: ${RABBITMQ_IMAGE}
          imagePullPolicy: ${LOCAL_DEP_IMAGE_PULL_POLICY}
          env:
            - name: RABBITMQ_DEFAULT_USER
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
                  key: RABBITMQ_USERNAME
            - name: RABBITMQ_DEFAULT_PASS
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
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
    app.kubernetes.io/name: ${RABBITMQ_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
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
    app.kubernetes.io/name: ${MINIO_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${MINIO_SERVICE}
      app.kubernetes.io/part-of: file-translation-manual-airgap
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${MINIO_SERVICE}
        app.kubernetes.io/part-of: file-translation-manual-airgap
    spec:
      containers:
        - name: minio
          image: ${MINIO_IMAGE}
          imagePullPolicy: ${LOCAL_DEP_IMAGE_PULL_POLICY}
          args: ["server", "/data", "--console-address", ":9001"]
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
                  key: MINIO_ACCESS_KEY
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: manual-deps-secrets
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
    app.kubernetes.io/name: ${MINIO_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
  ports:
    - name: api
      port: 9000
      targetPort: api
    - name: console
      port: 9001
      targetPort: console
EOF

note "Waiting for manual dependencies"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${POSTGRES_SERVICE}" --timeout="$TIMEOUT"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${RABBITMQ_SERVICE}" --timeout="$TIMEOUT"
kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${MINIO_SERVICE}" --timeout="$TIMEOUT"

if [ "$ALLOW_ONLINE_INFRA_PULL" = "1" ]; then
  note "Installing pgAdmin with online infra pull allowed for local manual rehearsal only"
  kubectl -n "$DEPS_NAMESPACE" create secret generic manual-pgadmin-secrets \
    --from-literal=PGADMIN_DEFAULT_EMAIL="$PGADMIN_DEFAULT_EMAIL" \
    --from-literal=PGADMIN_DEFAULT_PASSWORD="$PGADMIN_DEFAULT_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${PGADMIN_SERVICE}
  namespace: ${DEPS_NAMESPACE}
  labels:
    app.kubernetes.io/name: ${PGADMIN_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${PGADMIN_SERVICE}
      app.kubernetes.io/part-of: file-translation-manual-airgap
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${PGADMIN_SERVICE}
        app.kubernetes.io/part-of: file-translation-manual-airgap
    spec:
      containers:
        - name: pgadmin
          image: ${PGADMIN_IMAGE}
          imagePullPolicy: ${PGADMIN_IMAGE_PULL_POLICY}
          env:
            - name: PGADMIN_DEFAULT_EMAIL
              valueFrom:
                secretKeyRef:
                  name: manual-pgadmin-secrets
                  key: PGADMIN_DEFAULT_EMAIL
            - name: PGADMIN_DEFAULT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: manual-pgadmin-secrets
                  key: PGADMIN_DEFAULT_PASSWORD
            - name: PGADMIN_CONFIG_ALLOW_SPECIAL_EMAIL_DOMAINS
              value: "['local']"
          ports:
            - name: http
              containerPort: 80
          readinessProbe:
            httpGet:
              path: /misc/ping
              port: http
            initialDelaySeconds: 20
            periodSeconds: 10
            timeoutSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: ${PGADMIN_SERVICE}
  namespace: ${DEPS_NAMESPACE}
spec:
  selector:
    app.kubernetes.io/name: ${PGADMIN_SERVICE}
    app.kubernetes.io/part-of: file-translation-manual-airgap
  ports:
    - name: http
      port: 80
      targetPort: http
EOF

  kubectl -n "$DEPS_NAMESPACE" rollout status "deployment/${PGADMIN_SERVICE}" --timeout="$TIMEOUT"

  note "Installing ArgoCD ${ARGOCD_VERSION} from pinned upstream manifest"
  kubectl apply -n "$ARGOCD_NAMESPACE" --server-side --force-conflicts -f "$ARGOCD_INSTALL_URL" >/dev/null
  while IFS= read -r resource || [ -n "$resource" ]; do
    [ -n "$resource" ] || continue
    kubectl -n "$ARGOCD_NAMESPACE" rollout status "$resource" --timeout="$TIMEOUT"
  done < <(kubectl -n "$ARGOCD_NAMESPACE" get deployment,statefulset -o name | sort)
else
  warn "Skipping pgAdmin and ArgoCD because ALLOW_ONLINE_INFRA_PULL is not 1"
  warn "pgAdmin/ArgoCD online install is for local manual rehearsal only."
  warn "In a real closed network, these images/manifests must already exist in the internal registry or be separately mirrored."
fi

pass "Manual airgap infra rehearsal dependencies are ready"
cat <<EOF

Dependency endpoints for values.closed.yaml:
postgresql:
  bundled: false
  host: ${POSTGRES_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local
  port: 5432

rabbitmq:
  bundled: false
  host: ${RABBITMQ_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local
  port: 5672

minio:
  bundled: false
  endpoint: http://${MINIO_SERVICE}.${DEPS_NAMESPACE}.svc.cluster.local:9000

secrets:
  existingSecret: file-translation-secrets

global:
  imagePullPolicy: Never

K9s:
  kubectl config use-context ${KUBE_CONTEXT}
  k9s --context ${KUBE_CONTEXT}

Namespaces:
  - ${DEPS_NAMESPACE}
  - ${APP_NAMESPACE}
  - ${ARGOCD_NAMESPACE}
EOF
