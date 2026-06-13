# RabbitMQ Reliability Notes

Last updated: 2026-06-13 KST

This document records the pre-Helm RabbitMQ reliability boundary. It does not implement Helm charts or RabbitMQ broker-level DLX/DLQ resources.

## Public Boundary

Frontend, Admin UI, users, and Uptime Kuma do not publish RabbitMQ messages.

```text
Frontend/Admin/User/Uptime Kuma
-> job-service API
-> PostgreSQL job state
-> job-service publishes internal RabbitMQ commands
-> workers
-> worker events
-> job-service
```

RabbitMQ remains an internal worker orchestration mechanism.

## Ack And Completion

For job-service-created commands:

```text
worker consumes command
-> worker claims stage through job-service
-> worker acks RabbitMQ after CLAIMED/no-op
-> worker does long-running work
-> worker heartbeats through job-service
-> worker publishes stage.completed or stage.failed
```

RabbitMQ ack means the command was durably accepted or durably no-opped by job-service. It does not mean the stage finished.

## Retry Backoff

Automatic retry is owned by job-service.

Default schedule:

```text
STAGE_RETRY_BACKOFF_SECONDS=60,300,900
```

When a running lease expires or a retryable non-email stage fails:

```text
stage status -> retry_pending
attempt -> next attempt
next_retry_at -> now + backoff
retry command publish -> only after a later reconcile sees next_retry_at <= now
```

This prevents retry storms without requiring RabbitMQ delayed exchanges before Helm.

## Logical DLQ

The current implementation stores a logical DLQ record in job/stage JSONB state:

```text
failed_attempts
last_failed_command
terminal_failure_reason
dlq_reason
failed_record
```

`/admin/health`, `/admin/jobs/{job_id}`, and `/jobs/{job_id}/stages` expose enough state for operators to identify the failed route stage and failed command metadata.

Physical RabbitMQ DLX/DLQ queues are still future Helm/local-stack work.

## Email Send

`email_send` is side-effecting. Stale or failed `email_send` does not auto-retry.

Reason:

- the provider call may have succeeded before the worker died
- duplicate sends are worse than a failed job requiring operator review
- a real `military_api` provider must still add provider-level idempotency

## Helm Queue Initialization

Helm/local-stack now includes a RabbitMQ queue initialization Job. The Job uses AMQP declare operations from the project `job-service` image and is idempotent when existing queue arguments match the requested policy.

The Job declares the contract command/event queues:

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
q.events.stage_completed
q.events.stage_failed
q.events.progress
```

The chart also has values for optional physical broker resources:

```text
command queue DLX/DLQ
event queue DLX/DLQ
TTL retry queues
quorum vs classic queue policy
RabbitMQ Management API metrics
```

Physical DLX/DLQ is disabled by default because current app publishers/consumers declare queues as durable queues without `x-dead-letter-*` arguments. If a queue is first created with DLX arguments and a worker later declares it without those same arguments, RabbitMQ rejects the declaration with `PRECONDITION_FAILED`. Keep `rabbitmq.queues.enableDlq=false` until the runtime queue declaration policy is updated to pass matching arguments or to use passive queue checks after init.

Logical DLQ remains the supported runtime mechanism:

```text
PostgreSQL JSONB job/stage state
-> failed_attempts
-> failed_record
-> dlq_reason
```

TTL retry queues are declared only as optional broker scaffolding; job-service still owns delayed retry/backoff through `next_retry_at`.
