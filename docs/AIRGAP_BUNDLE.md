# Airgap Bundle

Last updated: 2026-06-13 KST

This document records what to stage before moving the file-translation Helm deployment into a closed network. It does not include real military/internal API credentials or custom conversion libraries.

## Docker Images

Mirror these project images into the closed-network registry:

```text
petoo/file-translation-job-service:0.1.0
petoo/file-translation-pdf2docx-worker:0.1.0
petoo/file-translation-docx-extract-worker:0.1.0
petoo/file-translation-translate-worker:0.1.0
petoo/file-translation-docx-replace-worker:0.1.0
petoo/file-translation-libreoffice-worker:0.1.0
petoo/file-translation-pdf2hwpx-worker:0.1.0
petoo/file-translation-hwpx-worker:0.1.0
petoo/file-translation-email-worker:0.1.0
petoo/pdf2docx:0.5.13-py311-static
```

Local rehearsal also uses these dependency images when Kubernetes does not already provide PostgreSQL, RabbitMQ, and MinIO:

```text
postgres:16-alpine
rabbitmq:3.13-management
minio/minio:RELEASE.2025-02-07T23-21-09Z
```

`petoo/pdf2docx:0.5.13-py311-static` is the custom static anchored pdf2docx runtime. The `pdf2docx-worker` image is built on that runtime, and the chart also exposes `PDF2DOCX_IMAGE` so the relationship remains visible in rendered configuration.

## Helm Chart

The chart path is:

```text
charts/file-translation/
```

Primary values files:

```text
charts/file-translation/values.local.yaml
charts/file-translation/values.closed.example.yaml
charts/file-translation/values.closed.local-rehearsal.yaml
```

Use `values.closed.example.yaml` as the closed-network template. Use `values.closed.local-rehearsal.yaml` only for local rehearsal against Kubernetes-hosted external-style PostgreSQL/RabbitMQ/MinIO.

## Values

Closed-network values should disable bundled dependencies and point at externally managed services:

```yaml
secrets:
  create: false
  existingSecret: file-translation-runtime-secrets

rabbitmq:
  enabled: false
  external: true
  host: rabbitmq.internal.example

postgresql:
  enabled: false
  external: true
  host: postgresql.internal.example

minio:
  enabled: false
  external: true
  endpoint: https://minio.internal.example
```

Keep physical RabbitMQ DLX/DLQ off unless the application queue declaration policy is upgraded to declare matching `x-dead-letter-*` arguments at runtime:

```yaml
rabbitmq:
  queues:
    enableDlq: false
```

Replacement points are values-driven:

```yaml
email:
  provider: mock # smtp and military_api are documented replacement targets
  api:
    baseUrl: http://mail-api

pdf2hwpx:
  provider: placeholder
  customLibraryEnabled: false

pdf2docx:
  image: petoo/pdf2docx:0.5.13-py311-static

images:
  emailWorker:
    repository: registry.internal.example/file-translation/email-worker
  pdf2hwpxWorker:
    repository: registry.internal.example/file-translation/pdf2hwpx-worker
  pdf2docxWorker:
    repository: registry.internal.example/file-translation/pdf2docx-worker
```

`EMAIL_API_TOKEN`, `EMAIL_API_USERNAME`, `EMAIL_API_PASSWORD`, and `TRANSLATION_API_TOKEN` must come from Secret data, not values files.

## Secret

Create the runtime Secret in the application namespace before installing the chart:

```bash
kubectl -n file-translation create secret generic file-translation-runtime-secrets \
  --from-literal=RABBITMQ_USERNAME='<rabbitmq-user>' \
  --from-literal=RABBITMQ_PASSWORD='<rabbitmq-password>' \
  --from-literal=MINIO_ACCESS_KEY='<minio-access-key>' \
  --from-literal=MINIO_SECRET_KEY='<minio-secret-key>' \
  --from-literal=POSTGRES_USER='<postgres-user>' \
  --from-literal=POSTGRES_PASSWORD='<postgres-password>' \
  --from-literal=TRANSLATION_API_TOKEN='<translation-token>' \
  --from-literal=EMAIL_API_TOKEN='<email-token>' \
  --from-literal=EMAIL_API_USERNAME='<email-user>' \
  --from-literal=EMAIL_API_PASSWORD='<email-password>'
```

For local rehearsal only, `scripts/dev/helm-install-closed-rehearsal.sh` creates a test Secret with non-production local values in both the app namespace and the dependency namespace.

## External Requirements

PostgreSQL:

```text
host/port reachable from job-service
database exists or can be initialized by the provided user
POSTGRES_USER has read/write access to the file_translation database
```

RabbitMQ:

```text
AMQP host/port reachable from job-service, queue init Job, and workers
vhost exists
user can declare/passively inspect command and event queues
frontend/admin/user clients do not connect directly to RabbitMQ
```

MinIO:

```text
endpoint reachable from job-service, bucket init Job, workers, and any in-cluster upload driver
bucket exists, or minio.bucketInit.enabled=true can create it
access key can read/write objects under the configured bucket
```

## Queue Init Job

The Helm chart renders a RabbitMQ queue init Job when:

```yaml
rabbitmq:
  queues:
    init:
      enabled: true
```

The Job uses AMQP declarations from the `job-service` image. It declares configured command/event queues and retry TTL queues idempotently. It does not purge queues, delete queues, or expose RabbitMQ as a user-facing API.

## DLQ Policy

Physical RabbitMQ DLX/DLQ is off by default because current app consumers declare durable queues without the broker `x-dead-letter-*` arguments. Turning broker DLQ on first can cause RabbitMQ `PRECONDITION_FAILED` queue declaration errors.

Logical DLQ remains in PostgreSQL/job-service state. Check it through:

```bash
curl http://127.0.0.1:8080/admin/health
curl http://127.0.0.1:8080/admin/jobs?status=failed
```

Look for `failed_job_count`, `recent_failed_jobs`, `dlq_reason`, and stage failure metadata in job payloads.

## Monitoring

Register Uptime Kuma against job-service, not RabbitMQ:

```text
/healthz
/readyz
/admin/health
```

`/healthz` verifies process liveness. `/readyz` verifies required dependencies. `/admin/health` adds queue, job, and worker-derived operational summaries.

## Admin UI

Port-forward for local or restricted operator access:

```bash
kubectl -n file-translation port-forward svc/file-translation-job-service 8080:8080
```

Then open:

```text
http://127.0.0.1:8080/admin
```

In production, expose Admin UI only through trusted operator ingress/auth. RabbitMQ remains internal worker orchestration only.

## Smoke Order

Baseline local stack:

```bash
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
helm lint charts/file-translation
helm template file-translation charts/file-translation -f charts/file-translation/values.local.yaml
helm template file-translation charts/file-translation -f charts/file-translation/values.closed.example.yaml
scripts/dev/helm-install-local.sh
scripts/dev/smoke-helm-local.sh
```

Closed-network local rehearsal:

```bash
helm template file-translation charts/file-translation -f charts/file-translation/values.closed.local-rehearsal.yaml
scripts/dev/helm-install-closed-rehearsal.sh
scripts/dev/smoke-helm-closed-rehearsal.sh
```

Optional deeper route checks:

```bash
scripts/dev/smoke-hwpx-route-e2e.sh
scripts/dev/smoke-docx-route-e2e.sh
scripts/dev/smoke-pdf-route-e2e.sh
```
