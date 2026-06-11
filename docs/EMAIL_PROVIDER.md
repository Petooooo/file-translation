# Email Provider Strategy

Last updated: 2026-06-11 20:53 KST

## Goal

`email-worker` remains the final `email_send` stage, but the actual delivery mechanism must be replaceable. The project must not assume SMTP as the fixed production path because the closed-network target may require a military/internal mail API.

## Worker Flow

```text
email-worker consumes q.commands.email_send
-> fetches job details from job-service
-> checks job-service sendability
-> refuses to send cancelled/failed/expired/not-sendable jobs
-> resolves final artifacts from job metadata
-> reads or downloads MinIO artifacts for attachments
-> calls MailProvider
-> writes email_report.json for mock/local mode
-> publishes stage.completed or stage.failed
```

`email-worker` never publishes the next worker command. It only publishes stage events back to RabbitMQ.

## MailProvider Interface

Conceptual interface:

```text
send_mail(uid, to, subject, body, attachments, metadata) -> MailSendResult
```

`attachments` should be provider-neutral and may include MinIO object keys, downloaded local temp paths, content types, and display filenames.

## Providers

| Provider | Purpose | Status |
| --- | --- | --- |
| `mock` | Local development and smoke tests without real email delivery. | Default target for first implementation. |
| `smtp` | Optional provider for environments that explicitly need SMTP. | Later, optional. |
| `military_api` | Closed-network/internal mail API integration. | Later implementation; contract prepared now. |

The military/internal API adapter must not hard-code URL, token, headers, credentials, or timeout values.

## Sendability Gate

Before calling any provider, `email-worker` must call:

```text
GET /jobs/{job_id}/sendability
```

Do not send if the job is:

```text
cancel_requested
cancelled
failed
expired
completed
```

or if `job-service` returns `sendable=false` for any other reason.

## Local Mock Behavior

The mock provider should write this report to MinIO:

```text
{object_prefix}/reports/email_report.json
```

Example:

```text
2026-01-21/12345678/a8f3k2p9/reports/email_report.json
```

Minimal report:

```json
{
  "schema_version": "1.0",
  "job_id": "uuid-or-id",
  "provider": "mock",
  "status": "sent",
  "to": "user@example.local",
  "subject": "Translated files are ready",
  "attachments": [
    "2026-01-21/12345678/a8f3k2p9/05_export/final.docx",
    "2026-01-21/12345678/a8f3k2p9/05_export/final.pdf",
    "2026-01-21/12345678/a8f3k2p9/06_hwpx/final.hwpx"
  ],
  "sent_at": "2026-01-21T12:00:00Z"
}
```

## Configuration

ConfigMap values:

```text
EMAIL_PROVIDER=mock
EMAIL_API_BASE_URL=http://mail-api
EMAIL_API_TIMEOUT_SECONDS=30
EMAIL_FROM=no-reply@example.local
EMAIL_SEND_ENABLED=true
```

Secret values:

```text
EMAIL_API_TOKEN
EMAIL_API_USERNAME
EMAIL_API_PASSWORD
```

Closed-network example:

```text
EMAIL_PROVIDER=military_api
EMAIL_API_BASE_URL=http://internal-mail-api.namespace.svc.cluster.local
```

## Helm Values Shape

```yaml
email:
  provider: mock
  sendEnabled: true
  api:
    baseUrl: http://mail-api
    timeoutSeconds: 30
  from: no-reply@example.local
  existingSecret: ""
```

`values.local.yaml` should keep `provider: mock`. `values.closed.example.yaml` should show `provider: military_api` with placeholder values only.

## Implementation Roadmap

| Step | Status |
| --- | --- |
| Add `MailProvider` interface and `MockMailProvider`. | Completed in `feat/email-worker-provider`. |
| Add `email-worker --send-local` or equivalent local smoke command. | Completed. |
| Add `email-worker --consume` for `q.commands.email_send`. | Completed. |
| Add `job-service` sendability call before provider execution. | Completed. |
| Store mock `email_report.json` in MinIO. | Completed and live-smoked. |
| Publish `stage.completed` or `stage.failed`. | Completed and tested. |
| Add optional SMTP adapter only if explicitly needed. | Pending; do not implement unless requested. |
| Add military/internal API adapter after the real API contract is available. | Pending. |

## Current Implementation Checkpoint

Branch `feat/email-worker-provider` implements the local mock path:

- `EMAIL_PROVIDER=mock`
- `email-worker --send-local`
- `email-worker --consume`
- `GET /jobs/{job_id}/sendability` through `JOB_SERVICE_URL`
- MinIO upload to `{object_prefix}/reports/email_report.json`
- `stage.completed` with `outputs.email_report`
- `stage.failed` with `EMAIL_NOT_SENDABLE`, `EMAIL_SEND_DISABLED`, or `EMAIL_SEND_FAILED`

`smtp` and `military_api` remain provider names in the contract but are not implemented yet.

## Security Notes

- Do not commit mail API tokens, usernames, passwords, or authorization headers.
- Do not log secrets.
- Do not include secrets in `email_report.json`.
- Use Kubernetes Secret or `existingSecret` for provider credentials.
