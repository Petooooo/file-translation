# Closed-Network Deployment Notes

Last updated: 2026-06-13 KST

This document records deployment requirements for a closed-network environment. Helm work is still pending; this document defines requirements for that later work.

The target environment may already provide:

- k3s or Kubernetes
- MinIO
- RabbitMQ
- translation API
- PostgreSQL

The chart must support both bundled local dependencies and external closed-network dependencies.

## Public Boundary

Only `job-service` should be exposed to frontend/admin/user/Uptime Kuma networks.

```text
Frontend/Admin/User/Uptime Kuma
-> job-service
```

RabbitMQ, MinIO, PostgreSQL, and internal provider APIs should stay on internal networks unless a deliberate operational exception is made.

## Monitoring Exposure

Expose the monitoring surface through job-service:

```text
/healthz
/readyz
/admin/health
/admin/workers
/admin/queues
```

Recommended exposure:

- `/healthz` and `/readyz`: liveness/readiness monitors.
- `/admin/health`: Uptime Kuma JSON or keyword monitor.
- `/admin/workers` and `/admin/queues`: trusted operator dashboard/monitoring networks only.
- `/admin` and `/admin/jobs*`: operator networks only, with ingress/auth controls when Helm work starts.

RabbitMQ Management API is optional. The current job-service queue summary uses AMQP passive declare when RabbitMQ is enabled and reports `unacked_count=null` because AMQP passive declare does not expose unacked counts. Job-service owns delayed retry/backoff and logical DLQ records in PostgreSQL JSONB state; if broker-level unacked, DLX/DLQ, or detailed metrics become required, add optional Management API configuration later without exposing RabbitMQ to frontend/admin/user clients. See `docs/RABBITMQ_RELIABILITY.md` for the pre-Helm boundary.

## External RabbitMQ

Required configuration:

```text
RABBITMQ_HOST
RABBITMQ_PORT
RABBITMQ_VHOST
RABBITMQ_USERNAME
RABBITMQ_PASSWORD
RABBITMQ_TLS_ENABLED
```

`RABBITMQ_TLS_ENABLED` is a deployment requirement. Runtime code may need explicit TLS wiring before production closed-network use.

Optional monitoring configuration may be added later for RabbitMQ Management API metrics. It must not be required for basic queue existence/readiness checks.

Command queues:

```text
q.commands.pdf2docx
q.commands.docx_extract
q.commands.docx_translate
q.commands.docx_replace
q.commands.docx_export
q.commands.docx_marker
q.commands.pdf2hwpx
q.commands.hwpx_extract
q.commands.hwpx_translate
q.commands.hwpx_replace
q.commands.hwpx_export
q.commands.email_send
```

Event queues:

```text
q.events.stage_completed
q.events.stage_failed
q.events.progress
```

Queue names must stay aligned with `docs/CONTRACTS.md` and `services/common/ft_common/config.py`.

Reliability planning note:

- Queue initialization currently covers required queue names only.
- Before Helm/local-stack implementation, decide whether physical RabbitMQ DLX/DLQ, TTL, quorum/classic queue choice, and passive verification behavior are needed in addition to job-service-owned retry/backoff/logical DLQ state.
- Job-service-created long-running commands now use stage claim/early ack and should not depend on leaving command deliveries unacked until conversion/export completion.
- Stale lease recovery is owned by `job-service`; later Helm work can wire `POST /internal/reconcile/stale-leases` through a CronJob or keep the job-service background loop enabled.
- Direct legacy RabbitMQ commands without `command_id` are not production-safe and should not be used by frontend/admin/user tooling.
- See `docs/RELIABILITY_REPLAN.md`.

## Queue Initialization Strategy

Recommended Helm behavior:

```text
helm install/upgrade
-> run a queue initialization Job
-> declare exchanges/queues/bindings idempotently
-> existing queues count as success
```

The initialization Job can use either:

- RabbitMQ Management API
- AMQP declare operations

The Job should fail fast on authentication, TLS, vhost, or permission errors. It should not delete or purge existing queues during normal install/upgrade.

## External MinIO

Required configuration:

```text
MINIO_ENDPOINT
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET
MINIO_SECURE
```

Operational requirements:

- bucket exists or an init Job creates it idempotently
- lifecycle policy is defined by the operator
- object keys use `{YYYY-MM-DD}/{user_id}/{file_id}/...`
- clients do not infer keys and bypass `job-service`

For uploads, closed-network deployments should choose either:

- job-service mediated multipart upload
- job-service issued presigned upload URL

## External PostgreSQL

Required configuration:

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_SSLMODE
```

Current live smokes use a JSONB aggregate repository for route validation. Production deployment should keep `job-service` as the PostgreSQL owner and add migrations before introducing normalized tables or outbox reliability.

## Translation API

The translation provider should be configured through deployment values and secrets.

Required future shape:

```text
TRANSLATION_PROVIDER=mock
TRANSLATION_PROVIDER=http
TRANSLATION_API_BASE_URL
TRANSLATION_API_TIMEOUT_SECONDS
TRANSLATION_API_TOKEN
```

No internal API URL, token, or header belongs in source code.

## Email Provider

Closed-network mail delivery should use the `MailProvider` adapter boundary.

Expected shape:

```text
EMAIL_PROVIDER=mock
EMAIL_PROVIDER=smtp
EMAIL_PROVIDER=military_api
EMAIL_SEND_ENABLED=true
EMAIL_FROM
EMAIL_API_BASE_URL
EMAIL_API_TIMEOUT_SECONDS
EMAIL_API_TOKEN
```

`EMAIL_PROVIDER=military_api` is documented as a replacement target and is not implemented yet.

## Image Supply

Images currently validated locally:

- `petoo/file-translation-job-service:0.1.0`
- `petoo/file-translation-pdf2docx-worker:0.1.0`
- `petoo/file-translation-docx-extract-worker:0.1.0`
- `petoo/file-translation-translate-worker:0.1.0`
- `petoo/file-translation-docx-replace-worker:0.1.0`
- `petoo/file-translation-libreoffice-worker:0.1.0`
- `petoo/file-translation-pdf2hwpx-worker:0.1.0`
- `petoo/file-translation-hwpx-worker:0.1.0`
- `petoo/file-translation-email-worker:0.1.0`
- `petoo/pdf2docx:0.5.13-py311-static`

Closed-network image mirroring must include both project images and the custom static anchored `pdf2docx` base/runtime image.

## Helm Chart

The Helm chart now lives at:

```text
charts/file-translation/
```

Primary values files:

```text
charts/file-translation/values.yaml
charts/file-translation/values.local.yaml
charts/file-translation/values.closed.example.yaml
```

`values.local.yaml` enables bundled local PostgreSQL, RabbitMQ, and MinIO for k3d/k3s developer validation. `values.closed.example.yaml` disables bundled dependencies and shows external PostgreSQL/RabbitMQ/MinIO/provider/image replacement settings without real secrets.

Closed-network install shape:

```bash
helm upgrade --install file-translation charts/file-translation \
  --namespace file-translation \
  --create-namespace \
  -f charts/file-translation/values.closed.example.yaml \
  --set secrets.existingSecret=file-translation-runtime-secrets
```

The existing Secret must provide:

```text
RABBITMQ_USERNAME
RABBITMQ_PASSWORD
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
POSTGRES_USER
POSTGRES_PASSWORD
TRANSLATION_API_TOKEN
EMAIL_API_TOKEN
EMAIL_API_USERNAME
EMAIL_API_PASSWORD
```

The chart supports:

- local bundled dependencies for developer smoke tests
- external RabbitMQ
- external MinIO
- external PostgreSQL
- external translation API
- external/internal mail provider config
- queue initialization Job
- job-service background stale lease reconciler configuration
- optional RabbitMQ TTL retry queue scaffolding
- optional RabbitMQ DLX/DLQ settings if the application queue declaration policy is upgraded to pass matching queue arguments
- job-service Service/Ingress exposure for `/healthz`, `/readyz`, `/admin/health`, and restricted operator admin endpoints
- bucket initialization Job if required
- secrets via existing Secret references

Physical RabbitMQ DLX/DLQ is disabled by default in local and closed example values. The current app code declares its command/event queues as durable queues without `x-dead-letter-*` arguments. Enabling broker DLX on those same queues before updating the app declaration policy causes RabbitMQ `PRECONDITION_FAILED` errors. Job-service logical DLQ remains active through PostgreSQL JSONB state.

Queue init uses AMQP declare operations from the project `job-service` image. It does not require RabbitMQ Management API or external package downloads.

Local validation:

```bash
scripts/dev/helm-install-local.sh
scripts/dev/smoke-helm-local.sh
```
