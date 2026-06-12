# Reliability, Admin, and Usage Replan

Last updated: 2026-06-13 00:40 KST

Branch: `feat/monitoring-readiness`

Scope: this document started as an audit/replan and now records the first MVP implementation of long-running stage safety, stale lease recovery, and monitoring readiness. Helm chart work, real email provider integration, real `pdf2hwpx`, real `rhwp`, and real LibreOffice H2O export remain out of scope.

## Executive Summary

The current pipeline correctly keeps the public boundary centered on `job-service`:

```text
Frontend/Admin/User
-> job-service API
-> PostgreSQL job state
-> job-service RabbitMQ command publish
-> workers
-> worker events
-> job-service
```

Workers publish stage events only and do not publish the next worker command. That design should stay.

The original reliability gap was long-running command handling. `RabbitMQJsonConsumer.consume_forever(...)` used to call the worker handler and only send `basic_ack` after the handler returned. For long `pdf2docx`, `pdf2hwpx`, `docx_export`, and `hwpx_export` jobs, the command could stay unacked for the entire conversion/export. The MVP implementation now uses job-service-created `command_id` metadata to claim a stage before work, ack after the durable claim/no-op decision, heartbeat while work runs, no-op duplicate commands/events, and reconcile expired leases when a worker dies after ack.

Recommended design direction:

```text
RabbitMQ ack = command safely accepted after job-service stage claim is persisted
stage.completed = actual work finished
```

That means long-running workers claim a stage through `job-service`, ack the RabbitMQ command after the claim/no-op decision is durable, heartbeat/progress through `job-service`, and let `job-service` publish next-stage commands only after `stage.completed`.

## 2026-06-12 MVP Implementation Checkpoint

Implemented on `feat/long-running-stage-safety`:

- `job-service` now emits internal command metadata for job-service-created commands:
  - `command_id`
  - `idempotency_key`
  - `lease_seconds`
  - `max_attempts`
- `job-service` now exposes service-to-service stage safety APIs:
  - `POST /jobs/{job_id}/stages/{stage}/claim`
  - `POST /jobs/{job_id}/stages/{stage}/heartbeat`
- `StageState` now records:
  - `command_id`
  - `claim_id`
  - `idempotency_key`
  - `claimed_by`
  - `lease_until`
  - `last_heartbeat_at`
  - `max_attempts`
  - `progress`
  - `long_running`
  - `retry_count`
  - `retryable`
  - `last_error`
- Worker command consumers now use a shared runtime for job-service-created commands:

```text
worker consume command
-> job-service stage claim
-> claim/no-op decision persisted in PostgreSQL JSONB
-> RabbitMQ command ack
-> long-running work
-> heartbeat thread renews lease while work runs
-> worker publishes stage.completed or stage.failed
-> job-service publishes next command
```

Claim result enum:

```text
CLAIMED
ALREADY_COMPLETED
ALREADY_RUNNING
JOB_CANCELLED
MAX_ATTEMPTS_EXCEEDED
INVALID_STAGE
```

Default reliability values:

```text
STAGE_CLAIM_LEASE_SECONDS=300
STAGE_HEARTBEAT_INTERVAL_SECONDS=30
STAGE_MAX_ATTEMPTS=3
```

Duplicate/no-op policy:

- already completed stage command -> `ALREADY_COMPLETED`
- running stage with live claim/lease -> `ALREADY_RUNNING`
- `email_send` with any existing running claim -> `ALREADY_RUNNING`
- cancelled or cancel-requested job -> `JOB_CANCELLED`
- stale/duplicate `stage.completed` event for a non-current or already completed stage -> no downstream command
- event with mismatched `claim_id`, `command_id`, or `attempt` -> no downstream command
- attempt greater than `max_attempts` -> `MAX_ATTEMPTS_EXCEEDED` and failed terminal state

Compatibility note:

- Commands without `command_id` still run through the legacy ack-after-work path. This keeps standalone stage smoke scripts compatible because they publish direct synthetic worker commands without a job-service-created command envelope.
- Route-level E2E and production job-service-created commands include `command_id`, so they use the claim/early-ack path.

Remaining limits:

- Retry/backoff is bounded by `max_attempts`, and stale leases can be retried immediately by the reconciler. Delayed queue/backoff scheduling is not implemented.
- Lease expiry recovery exists through an internal endpoint and optional background loop. DLQ handling and Helm CronJob wiring remain future work.
- Email duplicate send prevention is claim-based. Provider-level idempotency for `military_api` remains a replacement-provider requirement.
- Direct legacy RabbitMQ commands without `command_id` are intentionally not considered production-safe.

## 2026-06-12 Stale Lease Reconciler Checkpoint

Implemented on `feat/stale-lease-reconciler`:

- `job-service` exposes an internal recovery endpoint:
  - `POST /internal/reconcile/stale-leases`
- `job-service` can also run an optional background stale lease loop:
  - `STALE_LEASE_RECONCILER_ENABLED=true` by default for local/dev
  - `STALE_LEASE_RECONCILE_INTERVAL_SECONDS=60`
  - `STALE_LEASE_RETRY_BACKOFF_SECONDS=0`
- Running stages whose `lease_until` is earlier than the current time are reconciled from JSONB job state without a DB schema migration.
- If the job is `cancel_requested` or `cancelled`, the stale stage is marked cancelled and no retry command is published.
- If the current stage has attempts remaining, `attempts` is incremented, the old claim fields are cleared, and `job-service` publishes the retry command for the same stage.
- If `attempts >= max_attempts`, the stage and job move to failed terminal state.
- If the stale stage is `email_send`, the job fails terminally instead of auto-retrying, because the provider call may have succeeded before the worker died. This prevents duplicate sends until provider-level idempotency is available.
- Previous-attempt `stage.completed` or `stage.failed` events remain no-op because the active stage attempt no longer matches the stale event `attempt`, `command_id`, or `claim_id`.

Additional stage visibility fields:

```text
lease_expired
reconciled_at
retry_backoff_seconds
next_retry_at
last_reconcile_reason
stale_attempts
```

Reconciler limits:

- Retry is immediate. The current branch records retry/backoff metadata but does not implement delayed RabbitMQ retry queues.
- There is no DLQ policy yet.
- Helm CronJob wiring remains future work.
- Stale `email_send` is intentionally not auto-retried to avoid duplicate delivery.

## 2026-06-13 Monitoring Readiness Checkpoint

Implemented on `feat/monitoring-readiness`:

- job-service monitoring endpoints:
  - `GET /healthz`
  - `GET /readyz`
  - `GET /admin/health`
  - `GET /admin/workers`
  - `GET /admin/queues`
- `/healthz` is process-alive only and stays independent from PostgreSQL/RabbitMQ/MinIO dependency state.
- `/readyz` returns dependency-aware readiness and HTTP 503 when a required configured dependency is unhealthy.
- `/admin/health` summarizes dependency status, stale running count, failed job count, recent failed jobs, queue summary, and worker summary.
- `/admin/workers` is stage-activity-derived from job-service state because dedicated worker heartbeat is not implemented yet.
- `/admin/queues` uses AMQP passive declare when RabbitMQ is enabled and returns configured queue names with `status=skipped` when RabbitMQ is not enabled for the job-service process.
- RabbitMQ Management API is optional and not required for this MVP.
- The lightweight `/admin` skeleton shows a compact system health panel without exposing RabbitMQ credentials or publish controls to the browser.
- Route-level E2E scripts support optional `UPTIME_KUMA_PUSH_URL`; unset URLs do nothing and failed push calls do not fail local smoke validation.
- `scripts/dev/smoke-monitoring-readiness.sh` verifies healthy, degraded, and unhealthy monitoring states without requiring a real Uptime Kuma server.

Monitoring limits:

- Dedicated worker heartbeat is not implemented; worker status is inferred from stage activity.
- AMQP passive declare does not expose unacked counts, so queue summaries report `unacked_count=null`.
- Delayed retry/backoff, DLQ, Helm Service/Ingress exposure, and optional RabbitMQ Management API metrics remain future work.

## Current State

### job-service API

Current implemented API on this branch:

```http
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
POST /jobs/{job_id}/cancel
POST /jobs/{job_id}/retry
GET /jobs/{job_id}/sendability
POST /internal/reconcile/stale-leases
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
GET /healthz
GET /readyz
GET /admin/health
GET /admin/workers
GET /admin/queues
```

`POST /events` is available for local/testing event intake and RabbitMQ adapter plumbing. It is not a public frontend/admin API.

`/healthz` is process-alive only. `/readyz` is dependency-aware and returns HTTP 503 when a required configured dependency is unavailable. `/admin/health`, `/admin/workers`, and `/admin/queues` provide operator/Uptime Kuma summaries through job-service.

### Admin UI

`GET /admin` serves a lightweight HTML skeleton from `job-service`. It calls:

```http
GET /admin/jobs
GET /admin/jobs/{job_id}
POST /jobs/{job_id}/cancel
GET /admin/health
GET /admin/workers
GET /admin/queues
```

It shows job list, job detail JSON, stages, artifacts, error fields, a cancel action, and a compact system panel for health, dependency, queue, worker/stage, stale, and failed-job summaries. Retry API exists, but the UI does not yet expose a retry button. It does not directly access RabbitMQ or MinIO.

### RabbitMQ command/event

Command queues and event queues are aligned across docs and `services/common/ft_common/config.py`.

Command messages include:

```text
job_id
input_type
stage
attempt
object_prefix
source_lang
target_lang
input_object_key for the first route stage
```

Workers publish:

```text
stage.completed
stage.failed
translate.progress
```

Job-service-created commands now include `command_id`, `idempotency_key`, `lease_seconds`, and `max_attempts`. `claim_id`, `lease_until`, `last_heartbeat_at`, progress, stale lease reconciliation metadata, and retry/failure reason fields live in PostgreSQL job state after worker claim/reconcile actions. Delayed retry/backoff metadata such as `next_retry_at` is recorded for immediate retry but is still not scheduled through a delayed queue.

### Worker consume/ack 방식

Common worker command consumption uses `services/common/ft_common/rabbitmq.py`.

Current behavior for job-service-created commands:

```text
receive message
decode JSON
claim stage through job-service
basic_ack after CLAIMED or durable no-op response
run handler to completion if CLAIMED
heartbeat while work runs
publish stage.completed/stage.failed/progress from inside handler path
basic_nack(requeue=false) only when claim/decode fails before ack
```

Commands without `command_id` still use the legacy ack-after-work path for standalone stage smoke compatibility. Production and route-level E2E commands are created by `job-service` and include `command_id`.

There is also no explicit `basic_qos(prefetch_count=1)` or heartbeat tuning in the RabbitMQ connection helper.

### PostgreSQL JSONB repository

`JOB_SERVICE_REPOSITORY=postgres` stores one JSONB aggregate in a `jobs` table:

```text
jobs(job_id text primary key, payload jsonb not null, updated_at timestamptz not null)
```

The model includes stage status, attempts, timestamps, outputs, errors, job artifacts, progress, cancellation timestamps, claim owner, command/claim/idempotency ids, lease timestamps, max attempts, stale lease reconciliation fields, and retry metadata. It still does not include a durable event log, outbox table, DLQ rows, or separate normalized stage-attempt rows.

### E2E smoke

Completed route-level smokes prove the happy path for:

```text
HWPX route
DOCX route
PDF route
email_send terminal completed path
job-service admin API readiness
```

They also verify cancellation gates and no-send behavior in selected scenarios. Long-running safety smokes now simulate duplicate commands/events and stale lease recovery without creating 2,000-page files. They still do not simulate real RabbitMQ connection loss under a large converter process or delayed retry/backoff.

### email provider

`email-worker` uses a provider adapter. `mock` is implemented. `smtp` and `military_api` are documented replacement targets.

Before provider call, `email-worker` claims `email_send` through job-service and then calls:

```http
GET /jobs/{job_id}/sendability
```

This prevents sends when the job is already terminal or not at `email_send`. The stage claim prevents duplicate concurrent `email_send` commands from calling the provider while a send is already in progress or after `email_send` is completed.

### pdf2hwpx placeholder/custom replacement point

`pdf2hwpx-worker` currently generates a placeholder HWPX zip from marker DOCX. The replacement guide identifies the seam:

```text
services/pdf2hwpx-worker/pdf2hwpx_worker/artifacts.py
services/pdf2hwpx-worker/pdf2hwpx_worker/placeholder.py
```

The real closed-network custom library should replace placeholder generation without changing the public API or RabbitMQ contract.

## Risk Assessment

This table preserves the audit risks and records the MVP mitigation status. Remaining items still matter before production Helm/local-stack.

| Risk | Current/MVP behavior | Impact | Recommended fix | Priority | Files likely affected |
| --- | --- | --- | --- | --- | --- |
| Long-running `pdf2docx` | Job-service-created commands now claim/ack before conversion, heartbeat while processing, and can be retried/failed by stale lease reconciliation. | Direct legacy commands without `command_id` remain developer-smoke-only and can still ack after work. | Keep using job-service-created commands; add delayed backoff/DLQ and worker reconnect hardening before production. | P0 mitigated, P1 follow-up | `services/common/ft_common/rabbitmq.py`, `services/pdf2docx-worker`, `services/job-service` |
| Long-running `pdf2hwpx` | Same claim/ack path now applies; placeholder is fast today, but real custom library may be long-running. | Real library still needs heartbeat-friendly wrapper and idempotent output finalization. | Keep same claim/lease path; require custom library wrapper to preserve heartbeat/progress. | P0 mitigated, P1 follow-up | `services/pdf2hwpx-worker`, `docs/REPLACEMENT_GUIDE.md` |
| Long-running `docx_export` / `hwpx_export` | Export commands now claim/ack before export and heartbeat while processing. | Attempt-scoped temp artifact finalization is still not implemented. | Add output finalization guard if real export can overwrite good final artifacts after a crash. | P0 mitigated, P1 follow-up | `services/libreoffice-worker`, `services/job-service` |
| RabbitMQ connection lost | Command is acked after durable claim/no-op for job-service-created commands; stale lease recovery can retry/fail expired running stages. | Worker crash after ack is now recoverable, but retry is immediate and no DLQ exists yet. | Add worker reconnect tuning, delayed backoff, and DLQ policy before production hardening. | P0 mitigated, P1 follow-up | `services/common/ft_common/rabbitmq.py`, all workers, `services/job-service` |
| Unacked message redelivery | Reduced because route-level command ack no longer waits for long work. | Commands delivered before claim failure can still be nacked and retried. | Keep command handling idempotent through stage claim/idempotency key. | P0 mitigated | `services/job-service/orchestrator.py`, worker main modules |
| Duplicate stage execution | Workers claim with job-service before doing work when command has `command_id`. | Direct synthetic commands without `command_id` do not have production duplicate protection. | Keep direct RabbitMQ publish out of frontend/admin/user paths; use job-service commands only. | P0 mitigated | `services/job-service/api.py`, `orchestrator.py`, all worker consume paths |
| Duplicate artifact generation | Output keys are deterministic, so duplicate work overwrites the same MinIO keys. | Later duplicate can replace good output or hide first-run diagnostics. | Use deterministic final keys but write attempt-scoped temp keys first, then finalize once; record artifact attempt metadata. | P1 | worker artifact modules, MinIO helper, job-service artifact state |
| Duplicate in-route `stage.completed` event | `job-service` now ignores already completed, non-current, stale attempt, stale command, and stale claim events. | Event audit history is not persisted yet. | Add event/timeline persistence for operator visibility. | P0 mitigated, P1 follow-up | `services/job-service/orchestrator.py`, tests |
| Duplicate `email_send` command | `email_send` now claims before provider call; duplicate running/completed commands no-op. | If a provider sends mail and the worker dies before completion/report, provider-level idempotency is still needed. | Add provider idempotency key support for real `military_api`. | P0 mitigated, P1 follow-up | `services/email-worker`, `services/job-service`, `docs/REPLACEMENT_GUIDE.md` |
| Retry storm | Manual retry and stale lease retry are bounded by `max_attempts`; stale lease retry is immediate. | Automation can still retry quickly until `max_attempts` is exhausted because delayed retry queues are not implemented. | Add retryable stage policy, exponential backoff, delayed delivery, and operator override requirements. | P1 | `orchestrator.py`, API, Admin UI, docs/tests |
| Stale running stage | `lease_until` and `last_heartbeat_at` are stored; `POST /internal/reconcile/stale-leases` plus optional background loop retries/fails expired running stages; `/admin/health` reports stale running count. | Recovery and visibility exist, but DLQ/backoff/CronJob wiring and richer operator controls remain pending. | Add delayed retry/backoff, DLQ, and Helm CronJob or production scheduler wiring. | P0 mitigated, P1 follow-up | job-service repository/orchestrator, monitoring payloads |
| Admin UI cannot locate issue | Current UI shows job/stage/artifact/error JSON plus a compact system panel for dependency, queue, worker/stage, stale, and failed-job summaries. | Operators still lack timeline, attempt detail views, manual reconcile controls, and dedicated worker heartbeat. | Add timeline/attempt/event endpoints and compact operator controls after the monitoring MVP. | P1 | `services/job-service/api.py`, `docs/API.md`, `docs/ADMIN_UI.md` |
| E2E smoke differs from user upload flow | Route E2E smokes pre-seed MinIO and pass `input_object_key`; public upload APIs are still target docs. | A user cannot yet test the full upload-create-download flow through job-service only. | Add usage-flow smoke for job-service mediated or presigned upload path once selected. | P1 | `scripts/dev/smoke-usage-flow.sh`, `docs/USAGE.md`, job-service upload API |
| External RabbitMQ queue init ambiguous under reliability changes | Current docs list queues and init Job strategy, but no exchange/binding/dead-letter/retry queue policy is finalized. | Closed-network operators may create queues without DLX/TTL/backoff conventions. | Extend queue init plan with command/event exchange, DLQ, retry/backoff, quorum/classic choice, and passive verification. | P1 | `docs/CLOSED_NETWORK_DEPLOYMENT.md`, future Helm init Job |
| Uptime Kuma visibility | `/healthz`, `/readyz`, `/admin/health`, `/admin/workers`, and `/admin/queues` are implemented through job-service; route E2E smokes support optional `UPTIME_KUMA_PUSH_URL`. | Basic monitoring is available, but Helm exposure, auth, DLQ metrics, and dedicated worker heartbeat remain pending. | Wire endpoints into Helm Service/Ingress later and decide whether optional RabbitMQ Management API metrics are needed. | P0 mitigated, P1 follow-up | `services/job-service/api.py`, `services/job-service/job_service/monitoring.py`, `docs/MONITORING.md`, `docs/UPTIME_KUMA.md` |

## Proposed Architecture

### Design Principle

For long-running stages:

```text
RabbitMQ ack = command was durably accepted or durably no-opped
stage.completed = work actually finished and outputs are committed
```

Do not hold a RabbitMQ delivery unacked for the whole conversion/export.

### Stage Claim

Add a job-service-mediated claim API and repository method:

```http
POST /jobs/{job_id}/stages/{stage}/claim
```

Request fields:

```text
command_id
attempt
worker_id
idempotency_key
lease_seconds
```

Response cases:

```text
claimed
noop_completed
noop_not_current
noop_terminal
retry_later
conflict_attempt
```

Workers should ack the RabbitMQ command after receiving any durable `claimed` or `noop_*` result. If claim fails due to transient job-service/db failure, the worker may nack/requeue or let the connection fail according to a clear policy.

### Stage Lease

Extend stage state with:

```text
claim_id
claimed_by
claimed_at
lease_until
last_heartbeat_at
attempt
max_attempts
idempotency_key
command_id
next_retry_at
backoff_seconds
```

The lease lives in PostgreSQL/job-service state, not in RabbitMQ.

### Heartbeat and Progress

Workers should periodically call job-service or publish heartbeat/progress events:

```text
stage.heartbeat
progress
```

Minimum heartbeat fields:

```text
job_id
stage
attempt
claim_id
worker_id
last_progress
```

`job-service` updates `last_heartbeat_at`, extends `lease_until`, and keeps current progress visible to Admin UI.

### Completion and Failure

`stage.completed` and `stage.failed` events should include:

```text
job_id
stage
attempt
claim_id
idempotency_key
outputs
metrics
```

`job-service` should accept completion only when the event matches the active claim/attempt and the stage is still current/running. Duplicate or stale completion events should be recorded or ignored without publishing downstream commands.

### Retry and Backoff

Add policy:

```text
max_attempts per stage
retryable=true/false from stage.failed
next_retry_at
backoff_seconds
manual_retry_allowed
operator_override
```

Automated retry should be opt-in by stage and bounded. Manual retry should still go through `job-service`.

### Duplicate Command No-op

Worker command handling should begin with claim:

```text
receive command
claim stage via job-service
if noop: ack and exit
if claimed: ack and work
heartbeat/progress
complete/fail event
```

No worker should start MinIO download or provider calls before claim succeeds.

### Completed Stage No-op

`job-service` should no-op:

- duplicate command claim for a completed stage
- duplicate completed event for an already completed stage
- completed event whose attempt/claim_id is stale
- any event for terminal jobs, while optionally recording a duplicate/stale-event audit entry

### email_send Duplicate Prevention

`email_send` requires stronger protection because side effects leave the system.

Recommended flow:

```text
email-worker receives command
claim email_send
ack command after claim
job-service returns send token / claim_id
email-worker calls provider once
email-worker writes email_report.json
email-worker publishes stage.completed with claim_id and provider_message_id
job-service marks completed and records email_report/provider_message_id
duplicate email_send claim returns noop_in_progress or noop_completed
```

For real providers, use provider-level idempotency if available:

```text
provider idempotency key = job_id:email_send:attempt
```

If the provider does not support idempotency, job-service claim must be the single-send guard.

### Failed Terminal State

Introduce explicit failure categories:

```text
failed_retryable
failed_terminal
failed_exhausted
```

This can remain represented as `status=failed` plus fields in the first implementation, but Admin UI/API should expose why a retry is or is not allowed.

## Code Change Plan

### Phase A: Ack/idempotency audit only

Status: this document.

Deliverables:

- Record current ack-after-handler behavior.
- Record duplicate-event and duplicate-email gaps.
- Do not change runtime behavior.

### Phase B: Stage claim/lease repository methods

Status: implemented for claim, heartbeat, stale lease reconciliation, and event-driven complete/fail handling through existing orchestration methods.

Implemented job-service methods/endpoints:

```text
claim_stage(job_id, stage, attempt, command_id, worker_id, lease_seconds)
heartbeat_stage(job_id, stage, claim_id, progress)
handle_event(stage.completed/stage.failed/progress)
reconcile_stale_leases()
```

Likely files:

```text
services/job-service/job_service/models.py
services/job-service/job_service/repository.py
services/job-service/job_service/orchestrator.py
services/job-service/job_service/api.py
tests/test_job_service_routing.py
tests/test_job_service_api.py
```

Keep JSONB repository initially; avoid normalized schema migration until behavior is proven.

### Phase C: Worker command handling refactor

Status: implemented with a shared worker command runner:

```text
services/common/ft_common/worker_runtime.py
```

Responsibilities:

- parse command
- call job-service stage claim
- ack RabbitMQ command after claim/no-op
- run processor after claim
- send heartbeat/progress
- publish completed/failed event with claim_id

Likely worker files:

```text
services/pdf2docx-worker
services/docx-extract-worker
services/translate-worker
services/docx-replace-worker
services/libreoffice-worker
services/pdf2hwpx-worker
services/hwpx-worker
services/email-worker
```

### Phase D: Email duplicate-send protection

Status: implemented for job-service claim-based duplicate send prevention and stale `email_send` no-auto-retry. Provider-level idempotency key support for real `military_api` remains future work.

Likely files:

```text
services/email-worker/email_worker/artifacts.py
services/email-worker/email_worker/provider.py
services/email-worker/email_worker/job_service_client.py
services/job-service/job_service/orchestrator.py
docs/REPLACEMENT_GUIDE.md
```

### Phase E: Long-running safety smoke

Status: implemented and extended.

Implemented:

```text
scripts/dev/smoke-long-running-stage-safety.sh
scripts/dev/smoke-stale-lease-reconciler.sh
```

Smoke scenarios:

- duplicate command returns no-op
- heartbeat updates active claim
- stale lease is detected through JSONB stage state
- lease expiry republishes only within `max_attempts`
- previous-attempt completed event does not publish duplicate next command
- max-attempt stale lease fails terminally
- cancelled stale lease does not retry
- stale `email_send` fails without auto-retry to prevent duplicate sends

### Phase F: Admin API/UI visibility

Status: MVP implemented for system summary; timeline/events/attempt views remain future work.

Implemented:

```http
GET /admin/health
GET /admin/workers
GET /admin/queues
```

Still planned:

```http
GET /jobs/{job_id}/events
GET /jobs/{job_id}/timeline
GET /jobs/{job_id}/attempts
```

Expose:

```text
lease_until
last_heartbeat_at
attempt
max_attempts
next_retry_at
retryable
stale_duration
claim_id redacted/truncated
worker_id
```

### Phase G: Usage/replacement docs update

Update:

```text
docs/API.md
docs/ADMIN_UI.md
docs/USAGE.md
docs/INTEGRATION_GUIDE.md
docs/REPLACEMENT_GUIDE.md
docs/CLOSED_NETWORK_DEPLOYMENT.md
```

### Phase H: E2E smoke rerun

Rerun the full current suite:

```bash
python3 -m compileall -q services tests
python3 -m unittest discover -s tests
PYTHON_BIN=python3 scripts/dev/smoke-services.sh
PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh
scripts/dev/smoke-hwpx-route-e2e.sh
scripts/dev/smoke-docx-route-e2e.sh
scripts/dev/smoke-pdf-route-e2e.sh
```

### Phase I: Uptime Kuma/monitoring readiness

Status: MVP implemented.

Implemented summaries:

```text
healthy/degraded/unhealthy
stale running stages
queue existence and message/consumer counts when RabbitMQ is enabled
stage-activity-derived worker status
failed/retryable jobs
```

Monitoring still goes through `job-service`, not RabbitMQ. RabbitMQ Management API remains optional; AMQP passive declare does not expose unacked counts.

### Phase J: Helm/local-stack

Only after reliability and monitoring behavior is stable:

- add local-stack/Helm deployment
- add queue initialization Job
- add bucket initialization Job if needed
- add external dependency values
- add DLQ/retry queue settings according to the reliability design

## API/Admin UI Gap

Current branch implemented:

```http
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
POST /jobs/{job_id}/cancel
POST /jobs/{job_id}/retry
POST /jobs/{job_id}/stages/{stage}/claim
POST /jobs/{job_id}/stages/{stage}/heartbeat
POST /internal/reconcile/stale-leases
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
GET /admin/health
GET /admin/workers
GET /admin/queues
```

Recommended additions, in priority order:

| API | Priority | Purpose |
| --- | --- | --- |
| `POST /jobs/{job_id}/stages/{stage}/claim` | Implemented | Durable command acceptance and duplicate no-op. |
| `POST /jobs/{job_id}/stages/{stage}/heartbeat` | Implemented | Lease renewal and stale-stage detection. |
| `POST /internal/reconcile/stale-leases` | Implemented | Internal/admin recovery of expired running-stage leases. |
| `GET /jobs/{job_id}/timeline` | P1 | Operator/user chronological view. |
| `GET /jobs/{job_id}/attempts` | P1 | Retry/attempt/claim visibility. |
| `GET /jobs/{job_id}/events` | P1 | Event audit and duplicate/stale event diagnosis. |
| `GET /admin/health` | Implemented | Job-service dependency, stale-stage, failed-job, queue, and worker summary. |
| `GET /admin/workers` | Implemented | Stage-activity-derived worker status until dedicated heartbeat exists. |
| `GET /admin/queues` | Implemented | Queue existence/depth summary through job-service; unacked counts remain unavailable without optional Management API. |
| `POST /admin/jobs/{job_id}/retry` or reuse `POST /jobs/{job_id}/retry` with admin policy | P2 | Operator retry with policy explanation. |

Admin UI should add compact indicators for:

- current stage age
- lease state
- last heartbeat
- attempt/max attempts
- retryable vs terminal failure
- next retry time
- missing expected artifact
- email sent/report status

The claim, heartbeat, internal stale lease reconciler, monitoring endpoints, and compact Admin UI system panel are now implemented. Manual reconcile controls, timeline/events/attempt detail, and dedicated worker heartbeat remain future work.

## Usage / Integration Gap

Current docs are clear that users/frontends/admin tools must not use RabbitMQ. They document PDF/DOCX/HWPX request shapes, route stages, status queries, result artifact types, `email_report.json`, MinIO key shape, email provider replacement, `pdf2hwpx` replacement, external RabbitMQ variables, and queue init strategy.

Gaps to close before closed-network handoff:

| Area | Gap | Recommended follow-up |
| --- | --- | --- |
| PDF/DOCX/HWPX input | Route E2E smokes pre-seed MinIO and pass `input_object_key`. | Add a job-service-only usage smoke after choosing multipart or presigned upload. |
| File upload | Both upload options are documented, neither is implemented. | Pick MVP upload mode and document exact request/response. |
| Output download | Download API is target-only. | Implement `GET /jobs/{job_id}/download/{artifact_type}` or presigned download issuance. |
| email_report | Report shape is documented and mock-written. | Add duplicate-send prevention and provider idempotency expectations for `military_api`. |
| MinIO artifact keys | Key convention is clear. | Add artifact metadata size/content_type when repository supports it. |
| Military email library | Interface and replacement files are documented. | Add idempotency key and single-send rule to provider contract. |
| Custom `pdf2hwpx` library | Replacement seam is documented. | Add heartbeat/progress expectations for long custom conversion. |
| External RabbitMQ | Queue names/init strategy documented. | Add DLQ/retry/backoff/TTL/quorum guidance after reliability design. |
| Queue init verification | Init Job is future Helm work. | Add a preflight script/API that verifies queues via job-service/admin endpoint. |
| User pre-import test | Current smokes are developer-oriented. | Add `scripts/dev/smoke-usage-flow.sh` with job-service-only upload/create/status/download path. |

## Verification Plan

Minimum current validation for this implementation branch:

```bash
python3 -m compileall -q services tests
python3 -m unittest discover -s tests
git diff --check
```

Recommended quick smoke:

```bash
PYTHON_BIN=python3 scripts/dev/smoke-services.sh
PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh
PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh
```

After implementing reliability changes, rerun:

```bash
python3 -m compileall -q services tests
python3 -m unittest discover -s tests
PYTHON_BIN=python3 scripts/dev/smoke-services.sh
PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh
PYTHON_BIN=python3 scripts/dev/smoke-monitoring-readiness.sh
scripts/dev/smoke-hwpx-route-e2e.sh
scripts/dev/smoke-docx-route-e2e.sh
scripts/dev/smoke-pdf-route-e2e.sh
scripts/dev/smoke-stale-lease-reconciler.sh
```

New smoke candidates:

```bash
scripts/dev/smoke-long-running-stage-safety.sh
scripts/dev/smoke-stale-lease-reconciler.sh
scripts/dev/smoke-monitoring-readiness.sh
scripts/dev/smoke-usage-flow.sh
```

`smoke-long-running-stage-safety.sh`, `smoke-stale-lease-reconciler.sh`, and `smoke-monitoring-readiness.sh` should be gates before Helm/local-stack work resumes.

## Audit Answers

| Question | Current answer |
| --- | --- |
| RabbitMQ command consume 후 ack 시점 | For job-service-created commands with `command_id`, workers claim first and ack before long-running work. Legacy commands without `command_id` still ack after work. |
| Long-running stage unacked 여부 | Route-level commands no longer remain unacked for full handler duration. |
| Connection lost redelivery 가능성 | Reduced for route-level commands because ack happens after claim/no-op. If work fails after ack, stale lease reconciliation retries or fails from job-service state rather than RabbitMQ unacked delivery. |
| Duplicate command idempotency | Implemented for job-service-created commands through stage claim and no-op statuses. |
| Completed stage command no-op | Implemented for completed stage claims and duplicate/stale completed events. |
| Duplicate email_send after completed | Implemented through `email_send` claim no-op while running and after completed. Provider-level idempotency remains a future provider requirement. |
| retry/max_attempts/backoff | `max_attempts` is enforced for claims and stale lease recovery; delayed backoff/next_retry_at scheduling remains pending. |
| progress/heartbeat/lease | Generic claim lease and heartbeat fields are stored. Translate progress still exists. Stale lease recovery runs through an internal endpoint and optional background loop. |
| Admin API/UI visibility | Stage payload includes attempt/max_attempts/lease/heartbeat/progress/reconcile fields; `/admin/health`, `/admin/workers`, `/admin/queues`, and a compact system panel are implemented. Timeline/events/attempt detail remains pending. |
| E2E smoke vs user flow | E2E proves internal route flow but pre-seeds MinIO; upload/download user flow is not implemented. |
| User input/output docs | Conceptual docs exist; exact upload/download API is still target-only. |
| Military email sender library seam | Documented, but should add idempotency/single-send requirements. |
| Custom pdf2hwpx seam | Documented, but should add long-running heartbeat/progress requirements. |
| External RabbitMQ queue init | Queue list and init strategy are documented; DLQ/retry/backoff details are not. |
| Uptime Kuma/Admin problem visibility | Monitoring MVP is implemented through job-service: `/healthz`, `/readyz`, `/admin/health`, `/admin/workers`, `/admin/queues`, and optional `UPTIME_KUMA_PUSH_URL` route smoke reporting. Helm exposure/auth and richer metrics remain follow-up. |
