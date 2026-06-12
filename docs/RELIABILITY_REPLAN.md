# Reliability, Admin, and Usage Replan

Last updated: 2026-06-12 21:25 KST

Branch: `docs/reliability-admin-usage-replan`

Scope: audit and planning only. No worker ack behavior, repository behavior, Admin UI behavior, Helm chart, real email provider, or real `pdf2hwpx` implementation was changed on this branch.

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

The main reliability gap is long-running command handling. `RabbitMQJsonConsumer.consume_forever(...)` currently calls the worker handler and only sends `basic_ack` after the handler returns. For long `pdf2docx`, `pdf2hwpx`, `docx_export`, and `hwpx_export` jobs, the command can stay unacked for the entire conversion/export. If the RabbitMQ connection drops or the broker/client heartbeat times out, RabbitMQ may redeliver the command. Current worker command handlers do not claim a stage with `job-service` before work, do not persist a lease, and do not no-op duplicate commands. Current job-service event handling also does not treat duplicate in-route `stage.completed` events as idempotent. This can lead to duplicate conversion, duplicate downstream commands, retry storms, and duplicate email sends.

Recommended design direction:

```text
RabbitMQ ack = command safely accepted after job-service stage claim is persisted
stage.completed = actual work finished
```

That means long-running workers should claim a stage through `job-service`, ack the RabbitMQ command after the claim/no-op decision is durable, heartbeat/progress through `job-service`, and let `job-service` republish only when a lease expires or an explicit retry is requested.

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

`/healthz` and `/readyz` are currently the same process-level health payload on this branch. Dedicated monitoring endpoints such as `/admin/health`, `/admin/workers`, and `/admin/queues` are not in the `feat/admin-api-ui-readiness` checkpoint used for this planning branch.

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

There is no command id, idempotency key, lease id, claimed_at, lease_until, max_attempts, or backoff metadata.

### Worker consume/ack 방식

Common worker command consumption uses `services/common/ft_common/rabbitmq.py`.

Current behavior:

```text
receive message
decode JSON
run handler to completion
publish stage.completed/stage.failed/progress from inside handler path
basic_ack only after handler returns
basic_nack(requeue=false) only when the handler raises out of the wrapper
```

Because each worker catches processing exceptions and turns them into `stage.failed` events, most conversion failures still result in `basic_ack` after the failed event is published. For long-running successful work, the command is unacked until all MinIO downloads, conversion/export, uploads, and event publication finish.

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

Before provider call, `email-worker` calls:

```http
GET /jobs/{job_id}/sendability
```

This prevents sends when the job is already terminal or not at `email_send`. It does not prevent duplicate sends when two `email_send` commands are processed concurrently while the job is still `running/current_stage=email_send`, or when the first provider call succeeds but the completion event is lost before job-service marks the job completed.

### pdf2hwpx placeholder/custom replacement point

`pdf2hwpx-worker` currently generates a placeholder HWPX zip from marker DOCX. The replacement guide identifies the seam:

```text
services/pdf2hwpx-worker/pdf2hwpx_worker/artifacts.py
services/pdf2hwpx-worker/pdf2hwpx_worker/placeholder.py
```

The real closed-network custom library should replace placeholder generation without changing the public API or RabbitMQ contract.

## Risk Assessment

| Risk | Current behavior | Impact | Recommended fix | Priority | Files likely affected |
| --- | --- | --- | --- | --- | --- |
| Long-running `pdf2docx` | Worker holds the RabbitMQ command unacked until conversion, MinIO upload, and event publish finish. | Heartbeat timeout or connection loss can redeliver the command and rerun expensive conversion. | Add job-service stage claim/lease, ack after durable claim, heartbeat/progress while processing, idempotent completion. | P0 | `services/common/ft_common/rabbitmq.py`, `services/pdf2docx-worker`, `services/job-service` |
| Long-running `pdf2hwpx` | Same unacked command pattern; placeholder is fast today, but real custom library may be long-running. | Duplicate conversion and duplicate final HWPX artifact writes after redelivery. | Use same claim/lease path; require custom library wrapper to send heartbeat/progress. | P0 | `services/pdf2hwpx-worker`, `docs/REPLACEMENT_GUIDE.md` |
| Long-running `docx_export` / `hwpx_export` | Export command stays unacked through export and uploads. | LibreOffice/H2O work can be rerun; final artifacts may be overwritten; downstream commands can duplicate. | Stage claim/lease plus output idempotency checks before upload/finalize. | P0 | `services/libreoffice-worker`, `services/job-service` |
| RabbitMQ connection lost | Pika BlockingConnection may lose connection during long callback; no heartbeat processing/tuning is configured. | Unacked command may be redelivered while original work may still run or after it partially writes artifacts. | Decouple RabbitMQ ack from work completion; add worker reconnect policy and job-service lease recovery. | P0 | `services/common/ft_common/rabbitmq.py`, all workers |
| Unacked message redelivery | RabbitMQ can redeliver unacked command after consumer/channel failure. | Duplicate stage execution and duplicate downstream events. | Treat every command as at-least-once; make command handling idempotent through stage claim/idempotency key. | P0 | `services/job-service/orchestrator.py`, worker main modules |
| Duplicate stage execution | Workers do not ask job-service whether the stage is still runnable before doing work. | A completed or superseded stage can run again and overwrite artifacts. | Add `POST /jobs/{job_id}/stages/{stage}/claim`; workers no-op if claim returns completed/not current/terminal. | P0 | `services/job-service/api.py`, `orchestrator.py`, all worker consume paths |
| Duplicate artifact generation | Output keys are deterministic, so duplicate work overwrites the same MinIO keys. | Later duplicate can replace good output or hide first-run diagnostics. | Use deterministic final keys but write attempt-scoped temp keys first, then finalize once; record artifact attempt metadata. | P1 | worker artifact modules, MinIO helper, job-service artifact state |
| Duplicate in-route `stage.completed` event | `job-service` only no-ops terminal jobs. Duplicate `pdf2docx completed` while `docx_extract` is running can increment `docx_extract.attempts` and publish another `docx_extract`. | Duplicate downstream commands and possible retry storm. | Make `handle_event` idempotent: ignore stale completed events when stage already completed or when event attempt/idempotency key does not match active attempt. | P0 | `services/job-service/orchestrator.py`, tests |
| Duplicate `email_send` command | `sendability=true` while job is running at `email_send`; duplicate commands can both call provider before completion event lands. | Duplicate real email to users. | Add email send claim/finalization. Record `email_send_started_at`, `email_send_provider_message_id`, `email_report_key`; no-op duplicate after claim or report exists. | P0 | `services/email-worker`, `services/job-service`, `docs/REPLACEMENT_GUIDE.md` |
| Retry storm | Retry only checks `status=failed`; no max attempts, retryable flag policy, backoff, or next_retry_at. | Operators or automation can repeatedly republish failing stages. | Add max_attempts, retryable stage policy, exponential backoff, next_retry_at, operator override requirements. | P1 | `orchestrator.py`, API, Admin UI, docs/tests |
| Stale running stage | No lease_until/last_heartbeat_at or sweeper exists. | Job can remain running forever after worker death if command was acked early in a future refactor, or if failed event never arrives. | Add lease expiry and sweeper/reconciler that marks failed or republishes based on attempts/backoff. | P0 | job-service repository/orchestrator, new smoke |
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

This planning branch does not implement these APIs.

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

Minimum current validation for this planning branch:

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
| RabbitMQ command consume 후 ack 시점 | After the worker handler returns; for long-running work this means after conversion/export/upload/event publish. |
| Long-running stage unacked 여부 | Yes. The command remains unacked for the full handler duration. |
| Connection lost redelivery 가능성 | Yes. Commands are persistent and unacked messages may redeliver after consumer/channel failure. |
| Duplicate command idempotency | Not guaranteed. Workers do not claim/check current stage before work. |
| Completed stage command no-op | Not at worker start. job-service terminal jobs no-op events, but in-route duplicate completed events can republish downstream commands. |
| Duplicate email_send after completed | Completed jobs become non-sendable, but duplicates before completion can still send twice. |
| retry/max_attempts/backoff | Retry exists for failed jobs, but no max attempts/backoff/next_retry_at. |
| progress/heartbeat/lease | Translate progress exists. Generic heartbeat/lease is not stored. Idle log heartbeat is not job-stage heartbeat. |
| Admin API/UI visibility | Basic job/stage/artifact/error/cancel visibility exists. Lease, heartbeat, queue, worker, timeline, attempts detail are missing. |
| E2E smoke vs user flow | E2E proves internal route flow but pre-seeds MinIO; upload/download user flow is not implemented. |
| User input/output docs | Conceptual docs exist; exact upload/download API is still target-only. |
| Military email sender library seam | Documented, but should add idempotency/single-send requirements. |
| Custom pdf2hwpx seam | Documented, but should add long-running heartbeat/progress requirements. |
| External RabbitMQ queue init | Queue list and init strategy are documented; DLQ/retry/backoff details are not. |
| Uptime Kuma/Admin problem visibility | On this branch, only basic health/admin job APIs exist; richer monitoring remains a follow-up. |
