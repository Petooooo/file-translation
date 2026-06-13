# Monitoring

Last updated: 2026-06-13 00:40 KST

This document defines the monitoring surface for job-service centered operations.

Hard boundary:

```text
Frontend/Admin/User/Uptime Kuma
-> job-service API
-> job-service summarizes PostgreSQL/RabbitMQ/MinIO/job/worker state
```

RabbitMQ remains internal worker orchestration plumbing. MinIO and PostgreSQL remain internal dependencies. Monitoring clients should not publish RabbitMQ messages and should not require RabbitMQ credentials.

## Endpoints

### GET /healthz

Process-alive check.

- returns HTTP 200 while the job-service HTTP process can answer
- does not check PostgreSQL, RabbitMQ, or MinIO
- intended for liveness checks

Example:

```json
{
  "status": "ok",
  "service": "job-service",
  "environment": "local",
  "namespace": "file-translation"
}
```

### GET /readyz

Request-readiness check.

- checks dependencies required by the active job-service configuration
- keeps `status=ok` when readiness is healthy or degraded
- returns HTTP 503 and `status=unhealthy` when a required dependency is unavailable
- includes `overall_status=healthy|degraded|unhealthy`

Configured dependency rules:

- PostgreSQL is required when `JOB_SERVICE_REPOSITORY=postgres`.
- RabbitMQ is required when `JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq` or `JOB_SERVICE_EVENT_CONSUMER=rabbitmq`.
- MinIO is checked when `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` are configured.

### GET /admin/health

Operator health summary. This is the recommended Uptime Kuma JSON or keyword target.

Includes:

- `overall_status`
- `dependencies.job_service`
- `dependencies.postgresql`
- `dependencies.rabbitmq`
- `dependencies.minio`
- `job_summary`
- `stale_running_count`
- `retry_pending_count`
- `retry_pending_stages`
- `failed_job_count`
- `recent_failed_jobs`
- `queue_summary`
- `worker_summary`

Status policy:

- required dependency unavailable -> `unhealthy` and HTTP 503
- stale running stage present -> `degraded`
- retry pending stage present -> `degraded`
- failed job present -> `degraded`
- RabbitMQ queue check unhealthy -> `unhealthy`
- RabbitMQ queue check degraded -> `degraded`
- optional dependency skipped -> `healthy` unless another signal is degraded or unhealthy

### GET /admin/workers

Worker and stage summary.

Current MVP source:

```text
job stage state and worker events already processed by job-service
```

Current fields:

```text
worker
handled_stage
status
last_seen
last_error
counts
```

Current limitation:

- Dedicated worker heartbeat is not implemented yet.
- `last_seen` is stage-activity-derived from timestamps such as `started_at`, `completed_at`, `last_heartbeat_at`, and `reconciled_at`.

### GET /admin/queues

RabbitMQ queue summary through job-service.

When RabbitMQ is disabled for the job-service process, the endpoint returns configured queue names with `status=skipped`.

When RabbitMQ is enabled, the endpoint uses AMQP passive declare for configured command/event queues and returns:

```text
kind
stage
name
status
exists
message_count
consumer_count
unacked_count
metric_source
```

Current limitations:

- RabbitMQ Management API is optional and is not required in this MVP.
- AMQP passive declare does not expose unacked counts, so `unacked_count` is `null`.
- Queue initialization is still a future Helm/local-stack responsibility.

## Uptime Kuma Summary

Recommended Uptime Kuma monitors:

| Monitor | Type | Target | Expected |
| --- | --- | --- | --- |
| job-service liveness | HTTP | `/healthz` | HTTP 200 and `status=ok` |
| job-service readiness | HTTP | `/readyz` | HTTP 200 for ready; alert on HTTP 503 |
| system summary | HTTP keyword or JSON-style check | `/admin/health` | contains `healthy` or `degraded`; alert on `unhealthy` |
| HWPX route E2E | Push | route smoke with `UPTIME_KUMA_PUSH_URL` | push on success |
| DOCX route E2E | Push | route smoke with `UPTIME_KUMA_PUSH_URL` | push on success |
| PDF route E2E | Push | route smoke with `UPTIME_KUMA_PUSH_URL` | push on success |

## Push Monitor Pattern

Route-level E2E smokes support an optional push URL:

```bash
UPTIME_KUMA_PUSH_URL="https://uptime.example/api/push/..." scripts/dev/smoke-hwpx-route-e2e.sh
UPTIME_KUMA_PUSH_URL="https://uptime.example/api/push/..." scripts/dev/smoke-docx-route-e2e.sh
UPTIME_KUMA_PUSH_URL="https://uptime.example/api/push/..." scripts/dev/smoke-pdf-route-e2e.sh
```

If `UPTIME_KUMA_PUSH_URL` is unset, the scripts do nothing. If it is set but the push call fails, the local smoke success is not converted into a failure; the push URL is an optional reporting hook, not a dependency for validation.

Do not put Uptime Kuma push URLs or tokens in Git.

## Closed-Network Placement

Recommended placement:

```text
Uptime Kuma
-> internal HTTP route/service for job-service
```

Expose these endpoints inside the closed network:

```text
/healthz
/readyz
/admin/health
/admin/workers
/admin/queues
```

Expose `/admin` and `/admin/jobs*` only to authorized operator networks and protect them at ingress/auth layers when Helm/local-stack work starts.

## Current Validation

Local validation:

```bash
PYTHON_BIN=python3 scripts/dev/smoke-monitoring-readiness.sh
```

The smoke verifies:

- healthy `/healthz`
- healthy `/readyz`
- healthy `/admin/health`
- skipped queue summary when RabbitMQ is disabled
- event-derived worker summary
- stale running stage count appears as `degraded`, then becomes `retry_pending_count` until `next_retry_at` is due
- due retry publish clears `retry_pending_count`
- max-attempt stale failure appears in `failed_job_count` and `recent_failed_jobs`
- lightweight Admin UI monitoring links load
- unhealthy dependency reporting when RabbitMQ/MinIO are configured but unavailable

## Helm Exposure

The Helm chart exposes `job-service` through a ClusterIP Service by default.

Local access:

```bash
kubectl -n file-translation port-forward svc/file-translation-job-service 8080:8080
```

Kubernetes probes:

```text
livenessProbe  -> /healthz
readinessProbe -> /readyz
```

The local Helm smoke validates:

```bash
scripts/dev/smoke-helm-local.sh
```

It checks `/healthz`, `/readyz`, `/admin/health`, `/admin`, queue init Job completion, MinIO bucket init Job completion, and an in-cluster HWPX route E2E job through job-service.

Closed-network ingress or NodePort exposure is opt-in through values. `/admin` and job detail endpoints must stay restricted to operator networks until an auth layer is added.
