# Monitoring

Last updated: 2026-06-12 20:40 KST

Last updated: 2026-06-12 20:30 KST

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

- returns HTTP 200 while the job-service process can answer HTTP
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

- checks only dependencies that are configured for the current job-service process
- keeps `status=ok` for compatibility when readiness is healthy or degraded
- returns HTTP 503 and `status=unhealthy` when a required dependency is unavailable
- includes `overall_status=healthy|degraded|unhealthy`

Configured dependency rules:

- PostgreSQL is required when `JOB_SERVICE_REPOSITORY=postgres`.
- RabbitMQ is required when `JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq` or `JOB_SERVICE_EVENT_CONSUMER=rabbitmq`.
- MinIO is checked when `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` are configured.

### GET /admin/health

Operational health summary.

Includes:

- job-service process status
- PostgreSQL status
- RabbitMQ status
- MinIO status
- `overall_status`

Returns HTTP 503 only when required dependencies are unhealthy.

### GET /admin/workers

Worker status summary.

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
- `last_seen` and status are event-derived, not process-heartbeat-derived.

### GET /admin/queues

RabbitMQ queue summary.

When RabbitMQ is disabled for the job-service process, the endpoint returns the configured queue names with `status=skipped`.

When RabbitMQ is enabled, the endpoint checks configured command/event queues and returns:

```text
kind
stage
name
status
exists
message_count
consumer_count
```

Current limitation:

- The endpoint checks existing queues with RabbitMQ access from job-service.
- Queue initialization is still a future Helm/local-stack responsibility.

## Uptime Kuma Summary

Recommended Uptime Kuma monitors:

| Monitor | Type | Target | Expected |
| --- | --- | --- | --- |
| job-service liveness | HTTP | `/healthz` | HTTP 200 and `status=ok` |
| job-service readiness | HTTP | `/readyz` | HTTP 200 for ready; alert on HTTP 503 |
| system summary | HTTP keyword or JSON-style check | `/admin/health` | contains `healthy` or `degraded`; alert on `unhealthy` |
| HWPX route E2E | Push | route smoke wrapper | push on success |
| DOCX route E2E | Push | route smoke wrapper | push on success |
| PDF route E2E | Push | route smoke wrapper | push on success |

## Push Monitor Pattern

Uptime Kuma push monitors can be driven by scheduled E2E smoke commands.

Example:

```bash
scripts/dev/smoke-pdf-route-e2e.sh && \
  curl -fsS "$UPTIME_KUMA_PUSH_URL?status=up&msg=pdf-route-e2e-ok"
```

For failures, let the scheduled command fail and configure the scheduler to alert, or call the push URL with a failure message in the scheduler wrapper.

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
- lightweight Admin UI monitoring links
- unhealthy dependency reporting when RabbitMQ/MinIO are configured but unavailable
