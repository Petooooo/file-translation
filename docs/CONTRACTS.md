# Contracts

Last updated: 2026-06-10 12:35 KST

## Input Types

Valid `input_type` values:

```text
pdf
docx
hwpx
```

`job-service` rejects any other input type.

## Stage Names

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

## RabbitMQ Command Queues

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

## RabbitMQ Event Queues

```text
q.events.stage_completed
q.events.stage_failed
q.events.progress
```

## Command Message

Minimal shape:

```json
{
  "job_id": "uuid-or-id",
  "input_type": "pdf",
  "stage": "pdf2docx",
  "attempt": 1,
  "object_prefix": "2026-01-21/12345678/a8f3k2p9"
}
```

Workers may fetch detailed job/artifact state from `job-service` if needed. Commands must not contain secrets.

## Stage Completed Event

```json
{
  "event_type": "stage.completed",
  "job_id": "uuid-or-id",
  "input_type": "pdf",
  "stage": "pdf2docx",
  "outputs": {
    "converted_docx": "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx",
    "pdf2docx_report_json": "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json"
  },
  "metrics": {
    "duration_ms": 1234
  }
}
```

## Stage Failed Event

```json
{
  "event_type": "stage.failed",
  "job_id": "uuid-or-id",
  "input_type": "hwpx",
  "stage": "hwpx_export",
  "error_code": "HWPX_EXPORT_UNAVAILABLE",
  "error_message": "LibreOffice H2O export is not available in this environment",
  "retryable": false
}
```

## Progress Event

```json
{
  "event_type": "translate.progress",
  "job_id": "uuid-or-id",
  "input_type": "docx",
  "stage": "docx_translate",
  "total_units": 1200,
  "translated_units": 300,
  "failed_units": 0
}
```

## text_units.json

Minimal schema:

```json
{
  "schema_version": "1.0",
  "job_id": "uuid-or-id",
  "input_type": "docx",
  "source_lang": "en",
  "target_lang": "ko",
  "units": [
    {
      "uid": "unit-000001",
      "text": "Hello world",
      "location": {
        "type": "docx_run",
        "path": "word/document.xml",
        "paragraph_index": 0,
        "run_index": 0
      }
    }
  ]
}
```

`location` is route-specific. It must contain enough metadata for the matching replace stage to update the original document.

## translated_units.json

Minimal schema:

```json
{
  "schema_version": "1.0",
  "job_id": "uuid-or-id",
  "provider": "mock",
  "units": [
    {
      "uid": "unit-000001",
      "source": "Hello world",
      "translated": "안녕하세요 세계",
      "status": "translated"
    }
  ]
}
```

`uid` must match the corresponding `text_units.json` unit.

## MinIO Key Convention

Bucket:

```text
file-translation
```

Prefix:

```text
{YYYY-MM-DD}/{user_id}/{file_id}
```

Examples:

```text
2026-01-21/12345678/a8f3k2p9/input/original.pdf
2026-01-21/12345678/a8f3k2p9/input/original.docx
2026-01-21/12345678/a8f3k2p9/input/original.hwpx
2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx
2026-01-21/12345678/a8f3k2p9/02_extract/text_units.json
2026-01-21/12345678/a8f3k2p9/03_translate/translated_units.json
2026-01-21/12345678/a8f3k2p9/04_replace/translated.docx
2026-01-21/12345678/a8f3k2p9/04_replace/translated.hwpx
2026-01-21/12345678/a8f3k2p9/05_export/final.docx
2026-01-21/12345678/a8f3k2p9/05_export/final.pdf
2026-01-21/12345678/a8f3k2p9/05_export/marker.docx
2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md
```

## Job Metadata Contract

Minimum job fields:

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

## Config / Environment Names

Non-secret examples:

```text
APP_ENV
NAMESPACE
JOB_SERVICE_URL
RABBITMQ_HOST
RABBITMQ_PORT
RABBITMQ_VHOST
QUEUE_COMMANDS_PDF2DOCX
QUEUE_COMMANDS_DOCX_EXTRACT
QUEUE_COMMANDS_DOCX_TRANSLATE
QUEUE_COMMANDS_DOCX_REPLACE
QUEUE_COMMANDS_DOCX_EXPORT
QUEUE_COMMANDS_DOCX_MARKER
QUEUE_COMMANDS_PDF2HWPX
QUEUE_COMMANDS_HWPX_EXTRACT
QUEUE_COMMANDS_HWPX_TRANSLATE
QUEUE_COMMANDS_HWPX_REPLACE
QUEUE_COMMANDS_HWPX_EXPORT
QUEUE_COMMANDS_EMAIL_SEND
QUEUE_EVENTS_STAGE_COMPLETED
QUEUE_EVENTS_STAGE_FAILED
QUEUE_EVENTS_PROGRESS
MINIO_ENDPOINT
MINIO_BUCKET
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
TRANSLATION_PROVIDER
TRANSLATION_API_BASE_URL
TRANSLATION_API_TIMEOUT_SECONDS
PDF2DOCX_IMAGE
PDF2DOCX_ENABLE_REPORTS
HWPX_RHWP_ENABLED
HWPX_H2O_EXPORT_ENABLED
```

Secrets:

```text
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
RABBITMQ_USERNAME
RABBITMQ_PASSWORD
POSTGRES_USERNAME
POSTGRES_PASSWORD
TRANSLATION_API_TOKEN
SMTP_USERNAME
SMTP_PASSWORD
```

## job-service API Expectations

Initial API shape:

```text
POST /jobs
GET /jobs/{job_id}
POST /jobs/{job_id}/cancel
GET /jobs/{job_id}/sendability
```

`POST /jobs` accepts:

```json
{
  "user_id": "12345678",
  "input_type": "pdf",
  "source_lang": "en",
  "target_lang": "ko",
  "original_filename": "sample.pdf"
}
```

The file upload transport can be multipart HTTP or a pre-uploaded MinIO key, but the created job must record `input_object_key`.

The create response includes at least:

```json
{
  "job_id": "uuid-or-id",
  "status": "queued",
  "input_type": "pdf",
  "current_stage": "receive_input",
  "object_prefix": "2026-01-21/12345678/a8f3k2p9"
}
```
