# Architecture

Last updated: 2026-06-10 01:16 KST

## System Overview

The system is an MSA pipeline for file translation. It uses:

- `job-service` as the external API and pipeline orchestrator
- stage-specific stateless workers
- RabbitMQ command and event queues
- MinIO for all file artifacts
- PostgreSQL for job metadata, stage state, artifact keys, and progress
- a translation provider abstraction so local development can use a mock provider while production uses the internal API

## Service Responsibilities

## Phase 2 Skeleton Runtime

The initial service skeleton uses Python standard library only.

- shared config, logging, health, and MinIO object key helpers live under `services/common/ft_common`
- `job-service` exposes `/healthz`, `/readyz`, and `/config`
- workers provide smoke commands and long-running idle container processes
- no worker publishes next-stage commands
- no service connects to RabbitMQ, MinIO, or PostgreSQL until later phases

This keeps Phase 2 dependency-free while preserving the configuration and service boundaries needed for later integration.

### job-service

- Exposes APIs for create, query, and cancel/delete requests.
- Owns the PostgreSQL schema.
- Is the source of truth for job status.
- Publishes the first command after a job is accepted.
- Consumes worker events.
- Checks job state and cancellation before publishing each next command.
- Decides the next pipeline stage.

### Workers

Workers are stateless processors. They:

- consume one stage-specific command queue
- check job runnable state before starting work
- read input artifacts from MinIO
- write output artifacts to MinIO
- publish `stage.completed`, `stage.failed`, or progress events
- never publish the next stage command directly
- do not update PostgreSQL directly unless a later decision explicitly justifies it

## Pipeline

1. `pdf2docx-worker`: PDF input to converted DOCX.
2. `docx-extract-worker`: DOCX input to `text_units.json`.
3. `translate-worker`: `text_units.json` input to `translated_units.json`.
4. `docx-replace-worker`: converted DOCX and translated units to translated DOCX.
5. `libreoffice-worker`: normalize/save DOCX and export final DOCX/PDF.
6. `pdf2hwpx-worker`: placeholder HWPX generation until the custom library is available.
7. `email-worker`: sends final files only after checking sendability with `job-service`.

## RabbitMQ Design

Command queues:

```text
q.commands.pdf2docx
q.commands.extract
q.commands.translate
q.commands.replace
q.commands.libreoffice
q.commands.pdf2hwpx
q.commands.email
```

Event queues:

```text
q.events.stage_completed
q.events.stage_failed
q.events.progress
```

Minimal command message:

```json
{
  "job_id": "uuid-or-id",
  "stage": "pdf2docx"
}
```

Minimal completed event:

```json
{
  "event_type": "stage.completed",
  "job_id": "uuid-or-id",
  "stage": "pdf2docx",
  "outputs": {
    "converted_docx": "26-01-03/12345678/fileid/01_pdf2docx/converted.docx"
  }
}
```

Minimal progress event:

```json
{
  "event_type": "translate.progress",
  "job_id": "uuid-or-id",
  "total_units": 1200,
  "translated_units": 300,
  "failed_units": 0
}
```

## MinIO Object Keys

Bucket:

```text
file-translation
```

Required prefix format:

```text
{yy-mm-dd}/{user_id}/{file_id}/...
```

Required examples:

```text
26-01-03/12345678/a8f3k2p9/input/original.pdf
26-01-03/12345678/a8f3k2p9/01_pdf2docx/converted.docx
26-01-03/12345678/a8f3k2p9/02_extract/text_units.json
26-01-03/12345678/a8f3k2p9/03_translate/translated_units.json
26-01-03/12345678/a8f3k2p9/04_replace/translated.docx
26-01-03/12345678/a8f3k2p9/05_export/final.docx
26-01-03/12345678/a8f3k2p9/05_export/final.pdf
26-01-03/12345678/a8f3k2p9/06_hwpx/final.hwpx
```

`file_id` must be unique per uploaded file/job so the same user can upload multiple files on the same day.

## PostgreSQL MVP Schema

`job-service` owns the schema. Initial practical MVP:

- `jobs`: job id, user id, file id, object prefix, status, created/updated timestamps, cancel requested timestamp, error summary
- `job_stages`: job id, stage, status, attempts, started/completed timestamps, error details
- `artifacts`: job id, artifact type, MinIO bucket, object key, content type, size if known
- optional `outbox_events`: to be added when publisher reliability needs an outbox pattern

Initial implementation may use direct RabbitMQ publishing and document the reliability tradeoff. The outbox upgrade remains a planned enhancement.

## Cancellation Behavior

Recommended job statuses:

```text
queued
running
cancel_requested
cancelled
completed
failed
expired
```

Cancellation/delete request behavior:

- `job-service` marks the job as `cancel_requested` or `cancelled`.
- `job-service` does not publish further stage commands for cancelled jobs.
- workers check runnable state before starting work.
- already written MinIO artifacts remain.
- MinIO lifecycle/ILM handles old artifact deletion later.
- `email-worker` checks sendability before sending final files.

## Configuration

Non-secret values belong in ConfigMaps:

- namespace
- service URLs
- RabbitMQ host, port, vhost, queue names
- MinIO endpoint and bucket
- PostgreSQL host, port, and database name
- translation API base URL
- object prefix policy
- local/mock mode flags

Sensitive values belong in Secrets:

- MinIO access key and secret key
- RabbitMQ username and password
- PostgreSQL username and password
- translation API token if needed
- SMTP credentials if needed

Kubernetes service DNS should be used inside the cluster, for example:

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
