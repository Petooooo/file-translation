# Closed-Network Deployment Notes

Last updated: 2026-06-12 21:25 KST

This document records deployment requirements for a closed-network environment. Helm work is still pending; this document defines requirements for that later work.

The target environment may already provide:

- k3s or Kubernetes
- MinIO
- RabbitMQ
- translation API
- PostgreSQL

The chart must support both bundled local dependencies and external closed-network dependencies.

## Public Boundary

Only `job-service` should be exposed to frontend/admin/user networks.

```text
Frontend/Admin/User
-> job-service
```

RabbitMQ, MinIO, PostgreSQL, and internal provider APIs should stay on internal networks unless a deliberate operational exception is made.

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
- Before Helm/local-stack implementation, decide DLQ, retry/backoff, TTL, quorum/classic queue choice, and passive verification behavior.
- Long-running workers should not depend on leaving command deliveries unacked until conversion/export completion.
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

## Helm Requirements for Later

Helm is intentionally not implemented in the current PDF E2E and docs work.

Later Helm/local-stack work should support:

- local bundled dependencies for developer smoke tests
- external RabbitMQ
- external MinIO
- external PostgreSQL
- external translation API
- external/internal mail provider config
- queue initialization Job
- bucket initialization Job if required
- secrets via existing Secret references

Do not start Helm work until route-level E2E and operational contracts are stable.
