# Integration Guide

Last updated: 2026-06-12 22:08 KST

This guide is for frontend, admin, and system integrators.

## Integration Boundary

Only `job-service` is a public integration point.

```text
Client
-> job-service API
-> PostgreSQL state
-> RabbitMQ internal commands/events
-> workers
-> job-service status/result API
```

Do not integrate clients with RabbitMQ directly. RabbitMQ message schemas are internal contracts between `job-service` and workers.

## Frontend Flow

1. Upload the input file through `job-service` or through a job-service-issued presigned URL.
2. Call `POST /jobs`.
3. Store the returned `job_id`.
4. Poll `GET /jobs/{job_id}` or subscribe to a future status stream mediated by `job-service`.
5. When `status=completed`, call artifact/download APIs.
6. Show `reports/email_report.json` if the user needs send status.
7. Use `POST /jobs/{job_id}/cancel` for cancellation.
8. Use `POST /jobs/{job_id}/retry` when available and allowed by `job-service`.

## Route Selection

`input_type` controls the initial stage and route.

| input_type | initial stage | terminal path |
| --- | --- | --- |
| `pdf` | `pdf2docx` | DOCX stages, marker DOCX, `pdf2hwpx`, `email_send`, `completed` |
| `docx` | `docx_extract` | DOCX stages, marker DOCX, `pdf2hwpx`, `email_send`, `completed` |
| `hwpx` | `hwpx_extract` | HWPX stages, export placeholders, `email_send`, `completed` |

`input_type` is immutable after job creation.

## Internal Orchestration

The internal flow is event driven:

```text
job-service publishes initial command
worker consumes command
worker claims stage through job-service for job-service-created commands
worker acks RabbitMQ after durable claim/no-op
worker reads/writes MinIO artifacts
worker heartbeats/progresses while work runs
worker publishes stage.completed/stage.failed/progress
job-service consumes event
job-service updates PostgreSQL
job-service publishes next command or terminal state
```

Workers must not publish the next command directly.

Current reliability behavior:

- RabbitMQ command ack and actual stage completion are separated for job-service-created commands.
- Long-running stages expose job-service stage claim/lease/heartbeat state.
- Stale lease recovery is implemented through job-service internal reconciliation.
- Operational retry automation should still wait for delayed backoff/DLQ policy before production automation.

## Result Handling

Clients should rely on job-service state, not inferred object paths.

Important public fields:

```text
status
current_stage
error_stage
error_message
final_docx_key
final_pdf_key
final_hwpx_key
translated_hwpx_key
artifacts
stages
progress
```

Public download APIs should stream or issue short-lived URLs for approved artifacts.

## Cancellation and No-Send Rule

Cancellation is enforced by `job-service` and by `email-worker` sendability checks.

```text
cancel_requested
-> no new next-stage command after the next event
-> email-worker sendability=false
-> no real or mock send
```

The route-level E2E smokes verify both mid-route cancellation and email-stage no-send behavior.

## External Dependency Integration

Closed-network deployments may provide existing:

- k3s or Kubernetes
- MinIO
- RabbitMQ
- PostgreSQL
- translation API
- internal mail API

These dependencies should be configured through deployment values and secrets. Client integration does not change: clients still use `job-service`.

Reliability integration requirement:

- External clients should treat job status/timeline/attempt APIs as the source of truth when they are added.
- External clients must not infer stuck jobs from RabbitMQ queue state or publish repair commands directly.

## Current Smoke Coverage

Current route-level E2E smokes validate:

- HWPX route through `email_send` and `completed`
- DOCX route through `email_send` and `completed`
- PDF route through static anchored `pdf2docx`, downstream DOCX stages, `pdf2hwpx`, `email_send`, and `completed`

Current placeholder limits:

- DOCX PDF export uses placeholder output unless LibreOffice mode is enabled in a compatible image.
- `pdf2hwpx` output is a placeholder HWPX package.
- HWPX `rhwp` parsing/replacement is a local placeholder.
- Email delivery uses `EMAIL_PROVIDER=mock`.
