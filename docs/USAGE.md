# Usage

Last updated: 2026-06-12 11:00 KST

This document describes the user-facing workflow for PDF, DOCX, and HWPX translation jobs.

Important boundary:

```text
Users, frontends, and admin tools must not publish RabbitMQ messages.
Users, frontends, and admin tools call job-service API only.
RabbitMQ is internal worker orchestration plumbing.
```

## Public Entry Point

All user and frontend flows start at `job-service`.

```text
Frontend/Admin/User
-> job-service API
-> PostgreSQL job state
-> job-service publishes the initial RabbitMQ command
-> workers process MinIO artifacts
-> workers publish events
-> job-service updates status and publishes next commands
-> status/result API
```

## Creating Jobs

Target public API:

```http
POST /jobs
```

Example request:

```json
{
  "user_id": "12345678",
  "input_type": "pdf",
  "source_lang": "en",
  "target_lang": "ko",
  "original_filename": "sample.pdf",
  "email_to": "user@example.local"
}
```

Example response shape:

```json
{
  "job_id": "uuid-or-id",
  "file_id": "random-file-id",
  "status": "queued",
  "current_stage": "pdf2docx",
  "object_prefix": "2026-01-21/12345678/random-file-id"
}
```

Current smoke implementation note:

- The current local API returns the full job object plus the initial command envelope.
- The route-level E2E smokes pre-upload the input object to MinIO and pass `input_object_key` to `POST /jobs`.
- Multipart upload and presigned upload start APIs are target public API work, not RabbitMQ-facing work.

## Uploading Input Files

Two public upload patterns are acceptable. In both patterns, the frontend still talks to `job-service`, not RabbitMQ.

Option A: job-service mediated upload

```text
Frontend
-> POST /jobs with multipart file
-> job-service stores the file in MinIO
-> job-service creates the job and publishes the initial command
```

This is the simplest closed-network model when MinIO should stay fully private.

Option B: job-service issued presigned URL

```text
Frontend
-> job-service requests a presigned upload URL
-> frontend uploads the file to MinIO using that URL
-> frontend notifies job-service that upload is complete
-> job-service creates or starts the job and publishes the initial command
```

This is preferred for larger files when MinIO is reachable inside the closed network and direct object upload is operationally acceptable. The presigned URL must still be issued by `job-service`.

## PDF Request

Use:

```json
{
  "user_id": "12345678",
  "input_type": "pdf",
  "source_lang": "en",
  "target_lang": "ko",
  "original_filename": "sample.pdf",
  "email_to": "user@example.local"
}
```

The PDF route starts with the custom static anchored `pdf2docx` stage.

```text
pdf2docx
-> docx_extract
-> docx_translate
-> docx_replace
-> docx_export
-> docx_marker
-> pdf2hwpx
-> email_send
-> completed
```

Expected result artifacts:

```text
01_pdf2docx/converted.docx
reports/pdf2docx.report.json
reports/pdf2docx.report.md
05_export/final.docx
05_export/final.pdf
06_hwpx/final.hwpx
reports/email_report.json
```

## DOCX Request

Use:

```json
{
  "user_id": "12345678",
  "input_type": "docx",
  "source_lang": "en",
  "target_lang": "ko",
  "original_filename": "sample.docx",
  "email_to": "user@example.local"
}
```

The DOCX route skips initial PDF conversion.

```text
docx_extract
-> docx_translate
-> docx_replace
-> docx_export
-> docx_marker
-> pdf2hwpx
-> email_send
-> completed
```

Expected result artifacts:

```text
05_export/final.docx
05_export/final.pdf
05_export/marker.docx
06_hwpx/final.hwpx
reports/email_report.json
```

## HWPX Request

Use:

```json
{
  "user_id": "12345678",
  "input_type": "hwpx",
  "source_lang": "en",
  "target_lang": "ko",
  "original_filename": "sample.hwpx",
  "email_to": "user@example.local"
}
```

The HWPX route uses the direct HWPX placeholder path today and must not be forced through PDF or DOCX conversion at the beginning.

```text
hwpx_extract
-> hwpx_translate
-> hwpx_replace
-> hwpx_export
-> email_send
-> completed
```

Expected result artifacts:

```text
04_replace/translated.hwpx
05_export/final.docx
05_export/final.pdf
06_hwpx/final.hwpx
reports/email_report.json
```

## Checking Status

Target public API:

```http
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
```

Current local API:

```http
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
GET /jobs/{job_id}/sendability
```

The job status and `current_stage` are the user-facing source of truth.

Terminal success:

```text
status=completed
current_stage=completed
```

Terminal failures:

```text
status=failed
current_stage=failed
error_stage=<stage that failed>
error_message=<diagnostic message>
```

Cancelled:

```text
status=cancelled
current_stage=cancelled
```

## Downloading Results

Target public API:

```http
GET /jobs/{job_id}/download/{artifact_type}
```

Current local API exposes artifact keys through:

```http
GET /jobs/{job_id}/artifacts
GET /admin/jobs/{job_id}
```

Expected artifact types:

```text
final_docx
final_pdf
final_hwpx
translated_hwpx
email_report
pdf2docx_report_json
pdf2docx_report_markdown
```

`job-service` should either stream the object from MinIO or issue a short-lived download URL. The frontend must not infer MinIO keys and bypass `job-service` authorization.

## Email Result

Every completed route should write:

```text
{object_prefix}/reports/email_report.json
```

The report records:

- provider
- status
- recipient
- subject
- sent timestamp
- attachment object keys or attachment metadata
- optional provider message id

Local development uses `EMAIL_PROVIDER=mock`, so no real email is sent.

## Cancel

Public API:

```http
POST /jobs/{job_id}/cancel
```

Cancellation is cooperative:

- `job-service` records `cancel_requested`.
- `job-service` stops publishing new processing stage commands after the next worker event.
- `email-worker` calls sendability before sending and must not send if the job is cancelled or no longer sendable.

## Retry

Public API:

```http
POST /jobs/{job_id}/retry
```

Current MVP retry only accepts failed jobs and republishes the failed stage through `job-service`. Artifact existence checks and retry attempt limits are still future policy work.

## Administrator Escalation Points

When a user reports a failed or stuck job, administrators should check:

- `GET /admin/jobs/{job_id}` or `GET /jobs/{job_id}`
- `status`, `current_stage`, `error_stage`, and `error_message`
- stage attempts and timestamps
- MinIO artifact keys recorded by `job-service`
- `reports/email_report.json`
- worker logs for the failed stage
- RabbitMQ queue depth from internal operations tooling

Administrators still must not repair user jobs by manually publishing frontend-originated RabbitMQ messages. Repairs should go through `job-service` retry/cancel/admin APIs.
