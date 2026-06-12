# Uptime Kuma Guide

Last updated: 2026-06-13 00:40 KST

This guide describes how to register File Translation monitoring in Uptime Kuma.

Uptime Kuma should monitor `job-service`, not RabbitMQ directly.

```text
Uptime Kuma
-> job-service HTTP endpoint
-> job-service summarizes dependencies, queues, workers, and route state
```

## HTTP Monitors

### Liveness

```text
Type: HTTP(s)
URL: http://<job-service>/healthz
Expected: HTTP 200
```

Use this to detect whether the job-service process is alive. This check should stay green even when PostgreSQL, RabbitMQ, or MinIO is unavailable.

### Readiness

```text
Type: HTTP(s)
URL: http://<job-service>/readyz
Expected: HTTP 200
```

This checks configured dependencies. Uptime Kuma should alert on HTTP 503.

### Health Summary

```text
Type: HTTP(s) keyword
URL: http://<job-service>/admin/health
Keyword: healthy
```

Alternative keyword:

```text
degraded
```

Use a stricter monitor for `healthy` if degraded states should alert. Use a broader JSON/keyword approach if degraded states should remain visible but not page immediately.

`/admin/health` includes dependency status, stale running count, failed job count, recent failed jobs, queue summary, and worker summary.

## Push Monitors for E2E

Create separate Uptime Kuma push monitors for route-level E2E smokes:

```text
HWPX route E2E
DOCX route E2E
PDF route E2E
```

The route-level scripts support one optional environment variable:

```bash
UPTIME_KUMA_PUSH_URL="$UPTIME_KUMA_HWPX_PUSH_URL" scripts/dev/smoke-hwpx-route-e2e.sh
UPTIME_KUMA_PUSH_URL="$UPTIME_KUMA_DOCX_PUSH_URL" scripts/dev/smoke-docx-route-e2e.sh
UPTIME_KUMA_PUSH_URL="$UPTIME_KUMA_PDF_PUSH_URL" scripts/dev/smoke-pdf-route-e2e.sh
```

If `UPTIME_KUMA_PUSH_URL` is unset, the scripts skip the push. If the push call fails, the script logs the issue but keeps the local smoke result successful. Treat the push URL as an optional reporting hook, not a validation dependency.

Keep push URLs in scheduler secrets or local environment variables. Do not commit them.

## Operator Links

For dashboards, link to:

```text
GET /admin
GET /admin/jobs
GET /admin/health
GET /admin/workers
GET /admin/queues
```

`/admin` is a lightweight skeleton. Production access control belongs in the future ingress/auth layer.

## Why Not RabbitMQ Directly?

RabbitMQ is internal orchestration state. If Uptime Kuma or an external admin tool monitors or mutates RabbitMQ directly, it can:

- bypass job-service cancellation and retry policy
- confuse operators with queue state that lacks job context
- expose internal credentials
- encourage manual command publishing outside PostgreSQL state

The intended operational source of truth is `job-service`.

## Closed-Network Example

```text
Uptime Kuma pod or VM
-> internal DNS/service for job-service
-> /healthz, /readyz, /admin/health
```

Recommended exposure:

- expose `/healthz`, `/readyz`, and `/admin/health` to Uptime Kuma
- expose `/admin/workers` and `/admin/queues` only to trusted operator monitors or dashboards
- expose `/admin` and job detail APIs only to operator networks
- do not expose RabbitMQ Management UI to frontend/user networks
- do not expose MinIO credentials to Uptime Kuma unless a separate storage monitor is explicitly approved
