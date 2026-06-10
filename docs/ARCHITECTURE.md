# Architecture

Last updated: 2026-06-10 12:35 KST

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

### Workers

Workers are stateless processors. They:

- consume stage-specific command queues
- check job runnable state before starting work
- read input artifacts from MinIO
- write output artifacts to MinIO
- publish stage/progress events
- do not update PostgreSQL directly unless a later decision explicitly justifies it
- do not publish commands for the next stage

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
2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md
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
- object prefix policy
- pdf2docx report flag
- HWPX/H2O validation flags

Sensitive values belong in Secrets:

- MinIO access key and secret key
- RabbitMQ username and password
- PostgreSQL username and password
- translation API token if needed
- SMTP credentials if needed

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
