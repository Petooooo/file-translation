# Admin UI Requirements

Last updated: 2026-06-12 11:00 KST

The Admin UI may be a separate MSA or a lightweight UI served next to `job-service`.

Current MVP implementation:

```http
GET /admin
```

The current skeleton is served by `job-service` and calls only:

```http
GET /admin/jobs
GET /admin/jobs/{job_id}
POST /jobs/{job_id}/cancel
```

Hard boundary:

```text
Admin UI calls job-service API only.
Admin UI must not publish RabbitMQ messages.
Admin UI must not require RabbitMQ credentials.
```

RabbitMQ can be observed by internal platform tooling, but job repair actions must go through `job-service` admin APIs.

## MVP Requirements

| Requirement | Current status |
| --- | --- |
| Job list query | Implemented through `GET /admin/jobs`. |
| Job detail query | Implemented through `GET /admin/jobs/{job_id}`. |
| Display `input_type`, `status`, and `current_stage` | Implemented in the skeleton. |
| Display stage-by-stage status | Implemented as JSON detail. |
| Display progress | Exposed in the job payload; richer UI rendering remains future work. |
| Display `error_stage` and `error_message` | Implemented in summary/detail. |
| Display MinIO artifact keys recorded by `job-service` | Implemented as JSON detail. |
| Display `email_report.json` | Implemented when the artifact key is present. |
| Request cancel | Implemented through `POST /jobs/{job_id}/cancel`. |
| Request retry | API exists; UI button remains future work. |
| Filter `failed`, `cancelled`, and `completed` jobs | Implemented through the status filter; `cancel_requested` is also exposed. |

## Job List View

The list view should show:

```text
job_id
user_id
input_type
status
current_stage
original_filename
created_at
updated_at
completed_at
error_stage
```

Primary filters:

```text
status
input_type
current_stage
created_at range
user_id
failed only
cancelled only
completed only
```

## Job Detail View

The detail view should show:

- route and stage timeline
- stage attempts
- stage start/completion timestamps
- progress payload
- final artifact keys
- email report artifact
- error details
- cancel/retry availability

The UI may render MinIO object keys for operators, but downloads should still be mediated through `job-service` download APIs or short-lived URLs issued by `job-service`.

## Actions

Supported MVP actions:

```http
POST /jobs/{job_id}/cancel
POST /jobs/{job_id}/retry
```

Action rules:

- Cancel should be hidden or disabled for terminal jobs.
- Retry should be available only when `job-service` reports the job or failed stage is retryable.
- The UI should not let operators choose arbitrary RabbitMQ queues.
- The UI should not publish synthetic stage events directly.

Current skeleton exposes cancel. Retry is available as an API and should be added to the UI only after retry policy and operator copy are settled.

## Email Report Panel

When `reports/email_report.json` exists, the UI should show:

```text
provider
status
to
subject
sent_at
provider_message_id
attachments
```

Local `mock` email reports prove route termination in smoke tests. They do not prove real mail delivery.

## Failure Triage

The Admin UI should highlight:

- `error_stage`
- `error_message`
- missing expected artifacts
- stalled `current_stage`
- repeated attempts
- missing or failed `email_report`

Operational RabbitMQ depth and worker pod/container health can be linked from platform dashboards later, but remediation stays in `job-service`.
