# Architecture

Last updated: 2026-06-12 22:08 KST

## System Overview

The system is an MSA pipeline for file translation with three supported input types:

```text
pdf
docx
hwpx
```

Core services and infrastructure:

- `job-service`: external API, PostgreSQL owner, source of truth, pipeline router, event consumer, next-command publisher
- stateless workers: stage-specific processing services
- RabbitMQ: command queues and event queues
- MinIO: original, intermediate, report, and final artifacts
- PostgreSQL: job metadata, stage status, artifact keys, progress, cancellation, and optional outbox
- translation provider abstraction: local mock provider first, closed-network internal API later
- mail provider abstraction: local mock provider first, optional SMTP, closed-network military/internal API later

External users, frontend clients, and admin UI integrate with `job-service` only. RabbitMQ is internal to `job-service` and workers; it is not a frontend-facing interface.

## Orchestration Rule

Workers must not decide or enqueue the next stage.

```text
worker
-> publishes stage.completed / stage.failed / progress event
-> job-service consumes event
-> job-service checks job status and cancel state
-> job-service decides next stage from pipeline_route
-> job-service publishes next command queue
```

Long-running stage reliability rule:

```text
RabbitMQ command ack = command safely accepted or durably no-opped
stage.completed = actual processing finished and outputs committed
```

Current implementation: job-service-created commands include `command_id` and use a worker stage-claim path. Workers claim the stage through `job-service`, ack the RabbitMQ command after the durable claim/no-op response, heartbeat while processing, and publish `stage.completed` or `stage.failed` when actual work finishes. Direct legacy commands without `command_id` remain a developer-smoke compatibility path and are not production-safe.

## Input Routing

`job-service` determines the initial stage from `input_type`.

| input_type | initial_stage | route |
| --- | --- | --- |
| `pdf` | `pdf2docx` | PDF route, then DOCX route stages, marker DOCX, pdf2hwpx, email |
| `docx` | `docx_extract` | DOCX route stages, marker DOCX, pdf2hwpx, email |
| `hwpx` | `hwpx_extract` | Direct `rhwp` route, HWPX replace/export, email |

`input_type` is immutable after job creation.

## Service Responsibilities

### job-service

- validates create/query/cancel API requests
- stores job metadata and stage state in PostgreSQL
- validates `input_type` as one of `pdf`, `docx`, `hwpx`
- computes `pipeline_route`
- publishes the first command for the route
- consumes worker events
- gates every next-stage decision on job status and cancellation state
- publishes next commands
- owns sendability decisions used by `email-worker`
- owns stage claim, lease, heartbeat, max-attempt, and idempotency decisions for job-service-created long-running stage commands

### Workers

Workers are stateless processors. They:

- consume stage-specific command queues
- check job runnable state before starting work
- read input artifacts from MinIO
- write output artifacts to MinIO
- publish stage/progress events
- do not update PostgreSQL directly unless a later decision explicitly justifies it
- do not publish commands for the next stage
- claim a job-service-created stage command through `job-service` before doing long-running work and no-op duplicate/stale commands

### email-worker

`email-worker` is still a stage worker, but it must not be tied to one delivery mechanism such as SMTP.

Responsibilities:

- consume `q.commands.email_send`
- fetch job details, recipients, and final artifact keys from `job-service`
- call `job-service` sendability before any provider call
- claim `email_send` through `job-service` before any provider call
- stop without sending if the job is `cancelled`, `cancel_requested`, `failed`, `expired`, already `completed`, or otherwise not sendable
- download or reference final artifacts from MinIO as provider-specific attachments
- call the configured `MailProvider`
- write `reports/email_report.json` for the local mock provider
- publish `stage.completed` on successful send/report creation
- publish `stage.failed` on provider failure or non-sendable state

The first implementation should use a mock provider for local development. Optional SMTP and military/internal mail API providers must be adapters behind the same interface.

Conceptual provider boundary:

```text
send_mail(uid, to, subject, body, attachments, metadata) -> MailSendResult
```

Provider selection and all URLs, headers, tokens, credentials, and timeouts come from ConfigMap/Secret/Helm values.

## Stage Model

Final stage names for the revised contracts:

```text
receive_input

pdf2docx

docx_extract
docx_translate
docx_replace
docx_export
docx_marker
pdf2hwpx

hwpx_extract
hwpx_translate
hwpx_replace
hwpx_export

email_send

completed
failed
cancelled
```

`docx_translate` and `hwpx_translate` may be handled by the same `translate-worker`, but they remain distinct stage names so progress and retries are route-specific.

## Pipeline Routes

Detailed route definitions live in `docs/PIPELINE.md`.

Summary:

- PDF input uses `petoo/pdf2docx:0.5.13-py311-static` for static anchored PDF to DOCX conversion.
- DOCX input starts at DOCX text extraction and must not run initial PDF conversion.
- HWPX input starts with direct `rhwp` extraction and must not be forced through PDF/DOCX conversion.
- PDF and DOCX routes create a marker DOCX by replacing spaces with `¡` before `pdf2hwpx`.
- HWPX route validates LibreOffice H2O/HWPX read/export capability before treating PDF/DOCX export as reliable.

Current PDF/DOCX route implementation note:

- `libreoffice-worker --consume` handles `docx_export`.
- `libreoffice-worker --consume-marker` handles `docx_marker`.
- The two stages keep separate RabbitMQ queues and events even though they currently reuse the same image.
- `pdf2hwpx-worker --consume` handles `pdf2hwpx` with a placeholder HWPX package until the real custom library is available.

Current HWPX route implementation note:

- `hwpx-worker --consume-extract` handles `hwpx_extract`.
- `translate-worker --consume-hwpx` handles `hwpx_translate`.
- `hwpx-worker --consume-replace` handles `hwpx_replace`.
- `libreoffice-worker --consume-hwpx-export` handles `hwpx_export`.
- The local HWPX parser/replacer is a zip/XML stub until real `rhwp` is available.
- The local HWPX export path writes placeholder final DOCX/PDF artifacts and copies the final HWPX until LibreOffice H2O/HWPX support is implemented and validated.

## PostgreSQL Job Metadata

Minimum job metadata fields:

```text
job_id
user_id
file_id
input_type
source_lang
target_lang
status
current_stage
pipeline_route
object_prefix
original_filename
input_object_key
final_docx_key
final_pdf_key
final_hwpx_key
translated_hwpx_key
error_stage
error_message
created_at
updated_at
completed_at
cancel_requested_at
```

Recommended statuses:

```text
queued
running
cancel_requested
cancelled
completed
failed
expired
```

MVP tables:

- `jobs`: metadata above and source-of-truth status
- `job_stages`: job id, stage, status, attempts, timestamps, error detail
- `artifacts`: job id, artifact type, bucket, object key, content type, size if known
- optional `outbox_events`: later reliability upgrade for command/event publishing

## RabbitMQ Design

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

Message contracts live in `docs/CONTRACTS.md`.

Current implementation note:

- `job-service` has a `CommandPublisher` interface.
- `memory` mode is the default for local unit tests and smoke commands.
- `rabbitmq` mode declares durable command queues and publishes persistent JSON command messages.
- `JOB_SERVICE_EVENT_CONSUMER=rabbitmq` starts a RabbitMQ event consumer that decodes worker events, delegates orchestration to `job-service`, and ack/nack's event messages.
- `JOB_SERVICE_REPOSITORY=postgres` stores the job aggregate in PostgreSQL JSONB for live orchestration validation.
- Normalized stage tables and outbox-based reliable publishing are still future work.

## MinIO Object Keys

Bucket:

```text
file-translation
```

Required prefix format:

```text
{YYYY-MM-DD}/{user_id}/{file_id}/...
```

Required examples:

```text
2026-01-21/12345678/a8f3k2p9/input/original.pdf
2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx
2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json
2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json
2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx
2026-01-21/12345678/a8f3k2p9/05_export/final.docx
2026-01-21/12345678/a8f3k2p9/05_export/final.pdf
2026-01-21/12345678/a8f3k2p9/05_export/marker.docx
2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md
2026-01-21/12345678/a8f3k2p9/reports/email_report.json
```

`file_id` must be unique per uploaded file/job.

## Configuration

Non-secret values belong in ConfigMaps:

- namespace
- service URLs
- RabbitMQ host, port, vhost, queue names
- MinIO endpoint and bucket
- PostgreSQL host, port, and database name
- translation API base URL and provider mode
- email provider, API base URL, timeout, sender address, and send-enabled flag
- object prefix policy
- pdf2docx report flag
- DOCX export and marker mode flags
- HWPX/H2O validation flags

Sensitive values belong in Secrets:

- MinIO access key and secret key
- RabbitMQ username and password
- PostgreSQL username and password
- translation API token if needed
- email API token, username, and password if needed by the selected provider

Helm values must keep local and closed-network mail settings replaceable:

```yaml
email:
  provider: mock
  sendEnabled: true
  api:
    baseUrl: http://mail-api
    timeoutSeconds: 30
  from: no-reply@example.local
  existingSecret: ""
```

`values.local.yaml` should use the mock provider. `values.closed.example.yaml` should show how to select a military/internal API provider without including real closed-network addresses or credentials.

Inside Kubernetes, use service DNS names such as:

```text
job-service
rabbitmq
minio
postgresql
```

or fully qualified names such as:

```text
job-service.file-translation.svc.cluster.local
```

## Existing Skeleton Note

The existing Phase 2 Python skeletons are preserved. They are useful starting points, but their stage names and worker set must be aligned to this revised architecture before Phase 3 implementation proceeds.
