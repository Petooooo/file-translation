# job-service API

Last updated: 2026-06-13 00:40 KST

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
POST /jobs/{job_id}/stages/{stage}/claim
POST /jobs/{job_id}/stages/{stage}/heartbeat
POST /internal/reconcile/stale-leases
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
GET /admin/health
GET /admin/workers
GET /admin/queues
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

Reliability API note:

Long-running worker safety now uses service-to-service APIs before worker processing:

```http
POST /jobs/{job_id}/stages/{stage}/claim
POST /jobs/{job_id}/stages/{stage}/heartbeat
POST /internal/reconcile/stale-leases
```

Future operator/audit APIs still planned:

```http
GET /jobs/{job_id}/events
GET /jobs/{job_id}/timeline
GET /jobs/{job_id}/attempts
```

The claim/heartbeat endpoints are internal service-to-service APIs used by workers. `POST /internal/reconcile/stale-leases` is an internal recovery API for job-service operators or future scheduler/CronJob wiring. These are not frontend/admin/user queue-publish interfaces.

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
    "command_id": "uuid-or-id:pdf2docx:1",
    "idempotency_key": "uuid-or-id:pdf2docx:1",
    "lease_seconds": 300,
    "max_attempts": 3,
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
stage claim fields:
  attempt
  max_attempts
  command_id
  claim_id
  idempotency_key
  lease_until
  last_heartbeat_at
  long_running
  retry_count
  last_error
  lease_expired
  reconciled_at
  retry_backoff_seconds
  next_retry_at
  last_reconcile_reason
  stale_attempts
```

## POST /jobs/{job_id}/stages/{stage}/claim

Internal worker API. A worker calls this after consuming a job-service-created RabbitMQ command and before starting long-running work.

Request:

```json
{
  "command_id": "job-id:pdf2docx:1",
  "attempt": 1,
  "worker_id": "pdf2docx-worker:pdf2docx",
  "idempotency_key": "job-id:pdf2docx:1",
  "lease_seconds": 300,
  "max_attempts": 3
}
```

Response:

```json
{
  "claim_status": "CLAIMED",
  "should_process": true,
  "job_id": "job-id",
  "stage": "pdf2docx",
  "attempt": 1,
  "max_attempts": 3,
  "command_id": "job-id:pdf2docx:1",
  "claim_id": "job-id:pdf2docx:1",
  "idempotency_key": "job-id:pdf2docx:1",
  "lease_until": "2026-06-12T13:13:00+00:00",
  "last_heartbeat_at": "2026-06-12T13:08:00+00:00"
}
```

Claim statuses:

```text
CLAIMED
ALREADY_COMPLETED
ALREADY_RUNNING
JOB_CANCELLED
MAX_ATTEMPTS_EXCEEDED
INVALID_STAGE
```

Workers ack the RabbitMQ command after a durable `CLAIMED` or no-op response. They process work only when `should_process=true`.

## POST /jobs/{job_id}/stages/{stage}/heartbeat

Internal worker API. A claimed worker renews its lease while work runs.

Request:

```json
{
  "claim_id": "job-id:pdf2docx:1",
  "progress": 12,
  "lease_seconds": 300
}
```

Fine-grained progress is optional. A worker may keep progress unchanged until completion if the underlying converter does not expose progress.

## POST /internal/reconcile/stale-leases

Internal recovery API. This scans job-service state for `running` stages whose `lease_until` has expired.

Request body is optional:

```json
{
  "retry_backoff_seconds": 0
}
```

Current MVP response shape:

```json
{
  "status": "reconciled",
  "scanned_jobs": 3,
  "stale_stages": 1,
  "retried": 1,
  "failed": 0,
  "cancelled": 0,
  "published_commands": [
    {
      "queue": "q.commands.pdf2docx",
      "message": {
        "job_id": "job-id",
        "stage": "pdf2docx",
        "attempt": 2,
        "command_id": "job-id:pdf2docx:2"
      }
    }
  ]
}
```

Rules:

- expired running stage below `max_attempts` increments `attempts` and republishes the same stage command through `job-service`
- previous-attempt events are ignored because their `attempt`, `command_id`, or `claim_id` no longer matches the active stage
- expired running stage at `max_attempts` fails terminally
- cancelled/cancel-requested jobs do not retry
- stale `email_send` fails terminally and is not automatically retried, to avoid duplicate sends

## GET /jobs/{job_id}/stages

Returns stage timeline data.

Each stage should expose:

```text
stage
status
attempts
max_attempts
started_at
completed_at
error_message
outputs
command_id
claim_id
lease_until
last_heartbeat_at
progress
long_running
lease_expired
reconciled_at
last_reconcile_reason
stale_attempts
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
- Max attempts are enforced.
- Stale lease recovery is implemented through the internal reconciler endpoint/background loop.
- Retry backoff is metadata-only in this MVP; delayed queues and DLQ policy are not implemented yet.

## GET /jobs/{job_id}/download/{artifact_type}

Target API.

`job-service` should stream the MinIO object or issue a short-lived download URL. The frontend must not assemble MinIO keys from `object_prefix` and bypass `job-service`.

## Admin API

Implemented endpoints:

```http
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
GET /admin/health
GET /admin/workers
GET /admin/queues
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

## GET /healthz

Process liveness endpoint.

Rules:

- returns HTTP 200 while the job-service HTTP process is alive
- does not fail because PostgreSQL, RabbitMQ, or MinIO is unavailable
- suitable for Kubernetes/Uptime Kuma liveness checks

## GET /readyz

Request readiness endpoint.

Rules:

- checks dependencies that are required by the active job-service configuration
- returns HTTP 200 when required dependencies are healthy or only optional dependencies are skipped
- returns HTTP 503 when a required dependency is unhealthy
- `JOB_SERVICE_REPOSITORY=postgres` makes PostgreSQL required
- `JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq` or `JOB_SERVICE_EVENT_CONSUMER=rabbitmq` makes RabbitMQ required
- MinIO is checked when credentials are configured

## GET /admin/health

Operator health summary endpoint. This is the recommended Uptime Kuma JSON/keyword target.

Includes:

```text
overall_status
dependencies.job_service
dependencies.postgresql
dependencies.rabbitmq
dependencies.minio
job_summary
stale_running_count
failed_job_count
recent_failed_jobs
queue_summary
worker_summary
```

Status policy:

- required dependency unavailable -> `unhealthy` and HTTP 503
- stale running stage or failed job present -> `degraded`
- optional dependency skipped -> `healthy` unless another signal is degraded/unhealthy

## GET /admin/workers

Worker/stage summary endpoint.

Current MVP source:

```text
job stage state already stored by job-service
```

Dedicated worker heartbeat is not implemented yet. `last_seen` is derived from stage timestamps such as `started_at`, `completed_at`, `last_heartbeat_at`, and `reconciled_at`.

## GET /admin/queues

RabbitMQ queue summary endpoint.

Behavior:

- if RabbitMQ is disabled for this job-service process, returns configured queue names with `status=skipped`
- if RabbitMQ is enabled, checks queues with AMQP passive declare
- reports `message_count` and `consumer_count` when available
- reports `unacked_count=null` because AMQP passive declare does not expose unacked counts

RabbitMQ Management API is not a required dependency in this MVP. If future operations require unacked/dead-letter metrics, add optional management API configuration without exposing RabbitMQ to frontend/admin/user clients.

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
