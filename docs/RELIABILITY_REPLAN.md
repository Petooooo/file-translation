# Reliability, Admin, and Usage Replan

Last updated: 2026-06-12 22:08 KST

Branch: `feat/long-running-stage-safety`

Scope: this document started as an audit/replan and now records the first MVP implementation of long-running stage safety. Helm chart work, real email provider integration, real `pdf2hwpx`, real `rhwp`, and real LibreOffice H2O export remain out of scope.

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

The original reliability gap was long-running command handling. `RabbitMQJsonConsumer.consume_forever(...)` used to call the worker handler and only send `basic_ack` after the handler returned. For long `pdf2docx`, `pdf2hwpx`, `docx_export`, and `hwpx_export` jobs, the command could stay unacked for the entire conversion/export. The MVP implementation now uses job-service-created `command_id` metadata to claim a stage before work, ack after the durable claim/no-op decision, heartbeat while work runs, and no-op duplicate commands/events.

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

- Retry/backoff is bounded by `max_attempts`, but automatic delayed retry and `next_retry_at` scheduling are not implemented.
- Lease expiry visibility exists through stage state, but there is no sweeper/reconciler yet.
- Email duplicate send prevention is claim-based. Provider-level idempotency for `military_api` remains a replacement-provider requirement.
- Direct legacy RabbitMQ commands without `command_id` are intentionally not considered production-safe.

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
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
GET /healthz
GET /readyz
```

`POST /events` is available for local/testing event intake and RabbitMQ adapter plumbing. It is not a public frontend/admin API.

`/healthz` and `/readyz` are currently the same process-level health payload on this branch. Dedicated monitoring endpoints such as `/admin/health`, `/admin/workers`, and `/admin/queues` remain a later monitoring-readiness task.

### Admin UI

`GET /admin` serves a lightweight HTML skeleton from `job-service`. It calls:

```http
GET /admin/jobs
GET /admin/jobs/{job_id}
POST /jobs/{job_id}/cancel
```

It shows job list, job detail JSON, stages, artifacts, error fields, and a cancel action. Retry API exists, but the UI does not yet expose a retry button. It does not directly access RabbitMQ or MinIO.

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

Job-service-created commands now include `command_id`, `idempotency_key`, `lease_seconds`, and `max_attempts`. `claim_id`, `lease_until`, `last_heartbeat_at`, and progress live in PostgreSQL job state after a worker claim. Delayed retry/backoff metadata such as `next_retry_at` is still not scheduled automatically.

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

The model includes stage status, attempts, timestamps, outputs, errors, job artifacts, progress, and cancellation timestamps. It does not include stage claim owner, lease id, lease_until, last_heartbeat_at, max_attempts, next_retry_at, idempotency key, event log, command id, or outbox rows.

### E2E smoke

Completed route-level smokes prove the happy path for:

```text
HWPX route
DOCX route
PDF route
email_send terminal completed path
job-service admin API readiness
```

They also verify cancellation gates and no-send behavior in selected scenarios. They do not simulate 2,000-page long-running processing, RabbitMQ connection loss, ack timeout, redelivery, duplicate command delivery, lease expiry, or retry backoff.

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
| Long-running `pdf2docx` | Job-service-created commands now claim/ack before conversion and heartbeat while processing. | Direct legacy commands without `command_id` remain developer-smoke-only and can still ack after work. | Keep using job-service-created commands; add lease sweeper before production. | P0 mitigated, P1 follow-up | `services/common/ft_common/rabbitmq.py`, `services/pdf2docx-worker`, `services/job-service` |
| Long-running `pdf2hwpx` | Same claim/ack path now applies; placeholder is fast today, but real custom library may be long-running. | Real library still needs heartbeat-friendly wrapper and idempotent output finalization. | Keep same claim/lease path; require custom library wrapper to preserve heartbeat/progress. | P0 mitigated, P1 follow-up | `services/pdf2hwpx-worker`, `docs/REPLACEMENT_GUIDE.md` |
| Long-running `docx_export` / `hwpx_export` | Export commands now claim/ack before export and heartbeat while processing. | Attempt-scoped temp artifact finalization is still not implemented. | Add output finalization guard if real export can overwrite good final artifacts after a crash. | P0 mitigated, P1 follow-up | `services/libreoffice-worker`, `services/job-service` |
| RabbitMQ connection lost | Command is acked after durable claim/no-op for job-service-created commands. | If worker dies after ack, job can remain running until lease monitoring/retry is added. | Add worker reconnect policy plus job-service lease sweeper/recovery. | P0 mitigated, P1 follow-up | `services/common/ft_common/rabbitmq.py`, all workers |
| Unacked message redelivery | Reduced because route-level command ack no longer waits for long work. | Commands delivered before claim failure can still be nacked and retried. | Keep command handling idempotent through stage claim/idempotency key. | P0 mitigated | `services/job-service/orchestrator.py`, worker main modules |
| Duplicate stage execution | Workers claim with job-service before doing work when command has `command_id`. | Direct synthetic commands without `command_id` do not have production duplicate protection. | Keep direct RabbitMQ publish out of frontend/admin/user paths; use job-service commands only. | P0 mitigated | `services/job-service/api.py`, `orchestrator.py`, all worker consume paths |
| Duplicate artifact generation | Output keys are deterministic, so duplicate work overwrites the same MinIO keys. | Later duplicate can replace good output or hide first-run diagnostics. | Use deterministic final keys but write attempt-scoped temp keys first, then finalize once; record artifact attempt metadata. | P1 | worker artifact modules, MinIO helper, job-service artifact state |
| Duplicate in-route `stage.completed` event | `job-service` now ignores already completed, non-current, stale attempt, stale command, and stale claim events. | Event audit history is not persisted yet. | Add event/timeline persistence for operator visibility. | P0 mitigated, P1 follow-up | `services/job-service/orchestrator.py`, tests |
| Duplicate `email_send` command | `email_send` now claims before provider call; duplicate running/completed commands no-op. | If a provider sends mail and the worker dies before completion/report, provider-level idempotency is still needed. | Add provider idempotency key support for real `military_api`. | P0 mitigated, P1 follow-up | `services/email-worker`, `services/job-service`, `docs/REPLACEMENT_GUIDE.md` |
| Retry storm | Manual retry is now bounded by `max_attempts`; delayed backoff and `next_retry_at` are not implemented. | Operators or automation can still retry quickly until `max_attempts` is exhausted. | Add retryable stage policy, exponential backoff, next_retry_at, and operator override requirements. | P1 | `orchestrator.py`, API, Admin UI, docs/tests |
| Stale running stage | `lease_until` and `last_heartbeat_at` are stored; no sweeper exists yet. | A job can still remain running after worker death until an operator or later reconciler intervenes. | Add lease expiry sweeper/reconciler that marks failed or republishes based on attempts/backoff. | P0 | job-service repository/orchestrator, new smoke |
| Admin UI cannot locate issue | Current UI shows current stage, progress payload, artifacts, errors, and stages, but no queue state, worker heartbeat, lease age, stale stage warning, event timeline, or attempts detail view. | Operators may not know whether a job is processing, stuck, redelivered, or safe to retry. | Add admin health/workers/queues/timeline/attempts endpoints and compact UI display. | P1 | `services/job-service/api.py`, `docs/API.md`, `docs/ADMIN_UI.md` |
| E2E smoke differs from user upload flow | Route E2E smokes pre-seed MinIO and pass `input_object_key`; public upload APIs are still target docs. | A user cannot yet test the full upload-create-download flow through job-service only. | Add usage-flow smoke for job-service mediated or presigned upload path once selected. | P1 | `scripts/dev/smoke-usage-flow.sh`, `docs/USAGE.md`, job-service upload API |
| External RabbitMQ queue init ambiguous under reliability changes | Current docs list queues and init Job strategy, but no exchange/binding/dead-letter/retry queue policy is finalized. | Closed-network operators may create queues without DLX/TTL/backoff conventions. | Extend queue init plan with command/event exchange, DLQ, retry/backoff, quorum/classic choice, and passive verification. | P1 | `docs/CLOSED_NETWORK_DEPLOYMENT.md`, future Helm init Job |
| Uptime Kuma visibility | On this branch, monitoring endpoints beyond `/healthz` and `/readyz` are not implemented. | Uptime Kuma cannot yet see dependency, worker, queue, or stale stage status via job-service. | Add monitoring readiness endpoints after reliability state fields exist; expose through job-service only. | P2 | `services/job-service/api.py`, `docs/API.md`, `docs/ADMIN_UI.md` |

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

Add job-service methods:

```text
claim_stage(job_id, stage, attempt, command_id, worker_id, lease_seconds)
heartbeat_stage(job_id, stage, claim_id, progress)
complete_stage(job_id, stage, claim_id, outputs, metrics)
fail_stage(job_id, stage, claim_id, error, retryable)
expire_stale_leases(now)
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

Add a shared worker command runner:

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

Add email-specific claim/finalization and provider idempotency key support.

Likely files:

```text
services/email-worker/email_worker/artifacts.py
services/email-worker/email_worker/provider.py
services/email-worker/email_worker/job_service_client.py
services/job-service/job_service/orchestrator.py
docs/REPLACEMENT_GUIDE.md
```

### Phase E: Long-running safety smoke

Add:

```text
scripts/dev/smoke-long-running-stage-safety.sh
```

Smoke scenarios:

- fake long `pdf2docx` processor heartbeats while command is already acked
- duplicate command returns no-op
- stale lease is detected
- lease expiry republishes only within max attempts/backoff
- duplicate completed event does not publish duplicate next command
- duplicate `email_send` does not call provider twice

### Phase F: Admin API/UI visibility

Add or prioritize:

```http
GET /admin/health
GET /admin/workers
GET /admin/queues
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

After lease/heartbeat state exists, monitoring should summarize:

```text
healthy/degraded/unhealthy
stale running stages
queue depth
worker heartbeat freshness
failed/retryable jobs
```

Monitoring still goes through `job-service`, not RabbitMQ.

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
GET /admin/jobs
GET /admin/jobs/{job_id}
GET /admin
```

Recommended additions, in priority order:

| API | Priority | Purpose |
| --- | --- | --- |
| `POST /jobs/{job_id}/stages/{stage}/claim` | P0 | Durable command acceptance and duplicate no-op. |
| `POST /jobs/{job_id}/stages/{stage}/heartbeat` | P0 | Lease renewal and stale-stage detection. |
| `GET /jobs/{job_id}/timeline` | P1 | Operator/user chronological view. |
| `GET /jobs/{job_id}/attempts` | P1 | Retry/attempt/claim visibility. |
| `GET /jobs/{job_id}/events` | P1 | Event audit and duplicate/stale event diagnosis. |
| `GET /admin/health` | P1 | Job-service dependency and stale-stage summary. |
| `GET /admin/workers` | P1 | Worker heartbeat/event-derived worker status. |
| `GET /admin/queues` | P1 | Queue existence/depth/stale command summary through job-service. |
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

The claim and heartbeat APIs are now implemented. Timeline/events/attempt detail and monitoring endpoints remain future work.

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
scripts/dev/smoke-hwpx-route-e2e.sh
scripts/dev/smoke-docx-route-e2e.sh
scripts/dev/smoke-pdf-route-e2e.sh
```

New smoke candidates:

```bash
scripts/dev/smoke-long-running-stage-safety.sh
scripts/dev/smoke-monitoring-readiness.sh
scripts/dev/smoke-usage-flow.sh
```

`smoke-long-running-stage-safety.sh` should be the gate before Helm/local-stack work resumes.

## Audit Answers

| Question | Current answer |
| --- | --- |
| RabbitMQ command consume 후 ack 시점 | For job-service-created commands with `command_id`, workers claim first and ack before long-running work. Legacy commands without `command_id` still ack after work. |
| Long-running stage unacked 여부 | Route-level commands no longer remain unacked for full handler duration. |
| Connection lost redelivery 가능성 | Reduced for route-level commands because ack happens after claim/no-op. If work fails after ack, completion/failure is represented by job-service state/events rather than RabbitMQ unacked delivery. |
| Duplicate command idempotency | Implemented for job-service-created commands through stage claim and no-op statuses. |
| Completed stage command no-op | Implemented for completed stage claims and duplicate/stale completed events. |
| Duplicate email_send after completed | Implemented through `email_send` claim no-op while running and after completed. Provider-level idempotency remains a future provider requirement. |
| retry/max_attempts/backoff | `max_attempts` is enforced; delayed backoff/next_retry_at scheduling remains pending. |
| progress/heartbeat/lease | Generic claim lease and heartbeat fields are stored. Translate progress still exists. A sweeper is pending. |
| Admin API/UI visibility | Stage payload now includes attempt/max_attempts/lease/heartbeat/progress fields. Compact UI rendering, queue/worker/timeline views remain pending. |
| E2E smoke vs user flow | E2E proves internal route flow but pre-seeds MinIO; upload/download user flow is not implemented. |
| User input/output docs | Conceptual docs exist; exact upload/download API is still target-only. |
| Military email sender library seam | Documented, but should add idempotency/single-send requirements. |
| Custom pdf2hwpx seam | Documented, but should add long-running heartbeat/progress requirements. |
| External RabbitMQ queue init | Queue list and init strategy are documented; DLQ/retry/backoff details are not. |
| Uptime Kuma/Admin problem visibility | On this branch, only basic health/admin job APIs exist; richer monitoring remains a follow-up. |
