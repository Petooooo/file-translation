# job-service API

Last updated: 2026-06-12 21:25 KST

`job-service` is the only public API entry point for users, frontends, and admin UI.

```text
Frontend/Admin/User
-> job-service API
-> PostgreSQL job state
-> job-service publishes RabbitMQ commands
```

RabbitMQ queues are internal. Frontend, admin UI, and user clients must not publish commands to RabbitMQ and must not depend on RabbitMQ message schemas.

## Current Implemented API

The current lightweight local API implements:

```http
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
POST /jobs/{job_id}/cancel
POST /jobs/{job_id}/retry
GET /jobs/{job_id}/sendability
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
GET /healthz
GET /readyz
```

`POST /events` exists for local/testing event intake and RabbitMQ adapter plumbing. It is not a public frontend/admin API.

`GET /admin` serves a lightweight Admin UI skeleton. It calls `job-service` APIs only.

## Target Public API

The public API should converge on:

```http
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
POST /jobs/{job_id}/cancel
POST /jobs/{job_id}/retry
GET /jobs/{job_id}/download/{artifact_type}
GET /admin/jobs
GET /admin/jobs/{job_id}
```

`GET /jobs/{job_id}/sendability` is primarily for `email-worker` and internal service-to-service checks.

`GET /jobs/{job_id}/download/{artifact_type}` remains a target API and is not implemented in the current lightweight service.

Reliability planning note:

Long-running worker safety will need additional job-service APIs before Helm/local-stack work:

```http
POST /jobs/{job_id}/stages/{stage}/claim
POST /jobs/{job_id}/stages/{stage}/heartbeat
GET /jobs/{job_id}/events
GET /jobs/{job_id}/timeline
GET /jobs/{job_id}/attempts
GET /admin/health
GET /admin/workers
GET /admin/queues
```

These are proposed in `docs/RELIABILITY_REPLAN.md` and are not implemented on this planning branch.

## POST /jobs

Creates a job, stores job state in PostgreSQL, and publishes the initial route command.

Request:

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

Target response:

```json
{
  "job_id": "uuid-or-id",
  "file_id": "random-file-id",
  "status": "queued",
  "current_stage": "pdf2docx",
  "object_prefix": "2026-01-21/12345678/random-file-id"
}
```

Current local response shape:

```json
{
  "job": {
    "job_id": "uuid-or-id",
    "file_id": "random-file-id",
    "status": "running",
    "current_stage": "pdf2docx",
    "object_prefix": "2026-01-21/12345678/random-file-id"
  },
  "published_command": {
    "job_id": "uuid-or-id",
    "input_type": "pdf",
    "stage": "pdf2docx",
    "attempt": 1,
    "object_prefix": "2026-01-21/12345678/random-file-id"
  },
  "queue": "q.commands.pdf2docx"
}
```

The `published_command` field is useful for local smoke verification. Public clients should treat command details as internal and should not persist queue contracts.

Current accepted create fields:

```text
user_id
input_type
source_lang
target_lang
original_filename
file_id
input_object_key
```

Target additional create fields:

```text
email_to
upload_mode
```

## Input Upload Contract

The MVP must choose one public upload mode per deployment. Both keep RabbitMQ internal.

### Option A: Multipart Upload Through job-service

```text
POST /jobs multipart/form-data
```

`job-service` receives the file, writes it to MinIO, creates PostgreSQL state, and publishes the initial command.

Closed-network fit:

- Best when MinIO must remain fully private.
- Simpler firewall and auth model.
- `job-service` carries more upload bandwidth.

### Option B: Presigned Upload URL Issued by job-service

Suggested target flow:

```http
POST /jobs/uploads
PUT <presigned_minio_url>
POST /jobs
```

or:

```http
POST /jobs
PUT <presigned_minio_url>
POST /jobs/{job_id}/start
```

Closed-network fit:

- Best for larger files when MinIO is reachable from the client network.
- `job-service` still owns authorization and route start.
- Presigned URLs must be short lived and scoped to the expected object key.

Recommended closed-network default:

- Use presigned uploads when client-to-MinIO networking is allowed.
- Use job-service mediated upload when MinIO should not be exposed to client networks.
- Never expose RabbitMQ to clients for upload or job start.

## GET /jobs/{job_id}

Returns job metadata, status, current stage, stage state, artifact keys, progress, and errors.

Important fields:

```text
job_id
user_id
file_id
input_type
status
current_stage
object_prefix
original_filename
input_object_key
final_docx_key
final_pdf_key
final_hwpx_key
translated_hwpx_key
error_stage
error_message
stages
artifacts
progress
```

## GET /jobs/{job_id}/stages

Returns stage timeline data.

Each stage should expose:

```text
stage
status
attempts
started_at
completed_at
error_message
outputs
```

## GET /jobs/{job_id}/artifacts

Returns user/admin artifact listing.

The response should include:

```text
artifact_type
object_key
content_type
size
created_at
download_available
```

## POST /jobs/{job_id}/cancel

Requests cooperative cancellation.

Rules:

- Completed jobs remain completed.
- Running jobs move to `cancel_requested`.
- `job-service` will not publish the next processing command after a worker event if cancellation is pending.
- `email-worker` must call sendability before sending and must stop if sendability is false.

## POST /jobs/{job_id}/retry

Retries a failed job from its failed stage and publishes the retry command through `job-service`.

Minimum checks before publishing retry command:

- job is `failed` or retryable by policy
- target stage exists in the route
- job is not cancelled, completed, or expired

Current MVP behavior:

- default retry stage is `error_stage`
- optional request body may set `"stage"`
- `job-service` resets the failed stage to `running`
- downstream non-completed stages are reset to `pending`
- `job-service` publishes the retry command
- non-failed jobs return `409 retry_not_allowed`

Current limit:

- MinIO artifact existence and retry attempt policy are not enforced yet.
- Max attempts, retry backoff, lease expiry, and stale running-stage detection are not enforced yet.

## GET /jobs/{job_id}/download/{artifact_type}

Target API.

`job-service` should stream the MinIO object or issue a short-lived download URL. The frontend must not assemble MinIO keys from `object_prefix` and bypass `job-service`.

## Admin API

Implemented endpoints:

```http
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
```

Required filters:

```text
input_type
status
current_stage
failed
cancelled
completed
created_at range
user_id
```

Admin APIs expose operational detail but still must not expose RabbitMQ publish rights to the UI.

`GET /admin/jobs` returns:

```json
{
  "jobs": [
    {
      "job_id": "uuid-or-id",
      "user_id": "12345678",
      "file_id": "random-file-id",
      "input_type": "pdf",
      "status": "running",
      "current_stage": "pdf2docx",
      "original_filename": "sample.pdf",
      "created_at": "2026-06-12T00:00:00+00:00",
      "updated_at": "2026-06-12T00:00:00+00:00",
      "completed_at": null,
      "error_stage": null,
      "error_message": null
    }
  ],
  "count": 1,
  "filters": {
    "status": "running"
  }
}
```

Supported query filters:

```text
status
input_type
current_stage
user_id
```

`GET /admin/jobs/{job_id}` returns:

```text
job
summary
stages
artifacts
```
