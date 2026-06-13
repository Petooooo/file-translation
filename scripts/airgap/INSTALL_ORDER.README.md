# File Translation Airgap Install Order

Use this README from inside an extracted airgap bundle.

## 1. Verify Bundle Files

```bash
sha256sum -c SHA256SUMS
```

Or from a source checkout:

```bash
./scripts/airgap/check-airgap-bundle.sh .
```

## 2. Load Images

Docker target:

```bash
./scripts/airgap/load-airgap-bundle.sh .
```

containerd target:

```bash
LOAD_TARGET=ctr CTR_NAMESPACE=k8s.io ./scripts/airgap/load-airgap-bundle.sh .
```

k3s target:

```bash
LOAD_TARGET=k3s ./scripts/airgap/load-airgap-bundle.sh .
```

k3d receiver rehearsal target:

```bash
LOAD_TARGET=k3d K3D_CLUSTER=file-translation-airgap-recv ./scripts/airgap/load-airgap-bundle.sh .
```

If the closed network uses a private registry, load or retag/push images with the site-approved registry workflow, then update `values.closed.yaml` image repositories.

## 3. Prepare Values

Start from:

```text
values/values.closed.example.yaml
```

Copy it to an environment-specific file, then set:

```text
secrets.existingSecret
rabbitmq.host / port / vhost / tls
postgresql.host / port / database
minio.endpoint / bucket / secure
translation.api.baseUrl
email.provider / email.api.baseUrl
images.*.repository and tag overrides
```

Do not put secret values in the values file.

## 4. Create Secret

Copy and edit the example script outside Git-tracked source if needed:

```bash
cp scripts/create-secrets.example.sh /tmp/create-file-translation-secrets.sh
vi /tmp/create-file-translation-secrets.sh
NAMESPACE=file-translation SECRET_NAME=file-translation-runtime-secrets \
  /tmp/create-file-translation-secrets.sh
```

The example script intentionally refuses to run while placeholder values remain.

For a local receiver rehearsal bundle that includes PostgreSQL/RabbitMQ/MinIO images, the bundled rehearsal helper can create non-production runtime Secrets from environment variables and install an external-dependency-style stack:

```bash
RABBITMQ_USERNAME='file_translation' \
RABBITMQ_PASSWORD='replace-me-for-rehearsal-only' \
MINIO_ACCESS_KEY='file_translation' \
MINIO_SECRET_KEY='replace-me-for-rehearsal-only' \
POSTGRES_USER='file_translation' \
POSTGRES_PASSWORD='replace-me-for-rehearsal-only' \
TRANSLATION_API_TOKEN='replace-me-for-rehearsal-only' \
EMAIL_API_TOKEN='replace-me-for-rehearsal-only' \
EMAIL_API_USERNAME='rehearsal-user' \
EMAIL_API_PASSWORD='replace-me-for-rehearsal-only' \
  ./scripts/airgap/install-receiver-rehearsal.sh .
```

Do not use these sample values in a real deployment.

## 5. Install Helm Chart

```bash
helm upgrade --install file-translation chart/file-translation-*.tgz \
  --namespace file-translation \
  --create-namespace \
  -f values/values.closed.example.yaml \
  --wait \
  --wait-for-jobs \
  --timeout 10m
```

For production, use your environment-specific values file instead of the example file.

## 6. Check Jobs and Endpoints

```bash
kubectl -n file-translation wait --for=condition=complete job/file-translation-queue-init --timeout=10m
kubectl -n file-translation get job file-translation-minio-init
kubectl -n file-translation rollout status deployment -l app.kubernetes.io/part-of=file-translation --timeout=10m
kubectl -n file-translation port-forward svc/file-translation-job-service 8080:8080
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
curl http://127.0.0.1:8080/admin/health
```

Or run the bundled receiver health smoke:

```bash
./scripts/airgap/smoke-receiver-health.sh
```

RabbitMQ is internal worker orchestration only. Frontend, Admin UI, users, and Uptime Kuma should call job-service endpoints.
