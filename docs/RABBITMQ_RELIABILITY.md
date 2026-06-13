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

## Helm Follow-Up

During Helm/local-stack work, decide whether to add:

```text
command queue DLX/DLQ
event queue DLX/DLQ
queue TTL
quorum vs classic queue policy
RabbitMQ Management API metrics
CronJob calling POST /internal/reconcile/stale-leases
```

The queue initialization Job should make any chosen exchanges, queues, bindings, and dead-letter settings idempotently.
