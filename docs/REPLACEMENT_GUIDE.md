# Replacement Guide

Last updated: 2026-06-13 KST

This guide records replacement seams for closed-network integrations. It does not implement military/internal mail delivery or the real custom `pdf2hwpx` library.

## email-worker Provider Replacement

`email-worker` uses a provider adapter boundary.

Supported configuration names:

```text
EMAIL_PROVIDER=mock
EMAIL_PROVIDER=smtp
EMAIL_PROVIDER=military_api
```

Current implementation:

- `mock` is implemented.
- `smtp` is documented but not implemented.
- `military_api` is documented but not implemented.

Primary files:

```text
services/email-worker/email_worker/provider.py
services/email-worker/email_worker/artifacts.py
services/email-worker/email_worker/main.py
services/email-worker/email_worker/job_service_client.py
```

Provider interface:

```text
send_mail(uid, to, subject, body, attachments, metadata) -> MailSendResult
```

`MailSendResult` fields:

```text
provider
status
sent_at
provider_message_id
metadata
```

### Mock Provider

The mock provider:

- performs no real delivery
- returns `status=sent`
- creates a deterministic mock provider message id
- supports local and route-level smoke tests
- causes `email-worker` to write `{object_prefix}/reports/email_report.json`

### military_api Provider

When the closed-network internal mail API is available, add a provider implementation behind the existing `MailProvider` interface.

Do not change RabbitMQ command contracts for this replacement. Keep `email_send` as a worker stage and keep sendability owned by `job-service`.

Expected configuration:

```text
EMAIL_PROVIDER=military_api
EMAIL_SEND_ENABLED=true
EMAIL_FROM=<sender address or system identity>
EMAIL_API_BASE_URL=<internal API base URL>
EMAIL_API_TIMEOUT_SECONDS=<timeout>
EMAIL_API_TOKEN=<secret token, if used>
EMAIL_API_USERNAME=<secret username, if used>
EMAIL_API_PASSWORD=<secret password, if used>
EMAIL_API_TLS_CA_BUNDLE=<optional internal CA bundle path>
```

Secrets must be injected through Kubernetes Secret or the deployment secret mechanism. Do not commit internal URLs, headers, tokens, or credentials.

### Attachment Handling

Current mock mode records MinIO object keys as attachment metadata.

A real provider may require local files. In that case, the provider adapter or the email artifact layer should:

1. read final artifact keys from `job-service` sendability
2. download required MinIO objects to a per-job temporary directory
3. pass local file paths or bytes to the internal mail API client
4. delete temporary files after send/report generation

The sendability artifact order is:

```text
final_docx
final_pdf
final_hwpx
translated_hwpx
```

### email_report.json Rule

`email-worker` writes:

```text
{object_prefix}/reports/email_report.json
```

Minimum report fields:

```text
schema_version
job_id
provider
status
to
subject
attachments
sent_at
provider_message_id
```

Do not include secrets in the report.

### Sendability Flow

Before any provider call:

```text
email-worker
-> GET /jobs/{job_id}/sendability
-> send only if sendable=true
```

If the job is cancelled, failed, completed, expired, or not at `email_send`, the worker must not send.

Reliability requirement:

- The real `military_api` provider should accept or emulate an idempotency key such as `job_id:email_send:attempt`.
- `email-worker` now claims `email_send` through job-service before calling the provider for job-service-created commands.
- Duplicate `email_send` commands no-op while an email send is in progress or after the stage is completed.
- Stale `email_send` and retryable provider failures are not auto-retried by job-service; they fail terminally with logical DLQ metadata to prevent duplicate sends.
- Provider-level idempotency is still required for a real provider if a provider call succeeds and the worker dies before the completion event/report is recorded.

## pdf2hwpx Replacement

The current `pdf2hwpx-worker` is a placeholder for PDF/DOCX routes.

Primary files:

```text
services/pdf2hwpx-worker/pdf2hwpx_worker/main.py
services/pdf2hwpx-worker/pdf2hwpx_worker/artifacts.py
services/pdf2hwpx-worker/pdf2hwpx_worker/placeholder.py
services/pdf2hwpx-worker/Dockerfile
```

Current behavior:

- consumes `q.commands.pdf2hwpx`
- accepts `input_type=pdf` or `input_type=docx`
- downloads `{object_prefix}/05_export/marker.docx`
- writes `{object_prefix}/06_hwpx/final.hwpx`
- publishes `stage.completed` with `outputs.final_hwpx`
- output is a placeholder HWPX zip containing `placeholder.json` and `source/marker.docx`

Replacement target:

```text
marker DOCX
-> custom closed-network pdf2hwpx Python library
-> final.hwpx
```

### Integration Location

Replace the placeholder generation path inside:

```text
process_pdf2hwpx_command(...)
generate_placeholder_hwpx(...)
```

The replacement must preserve:

- command validation
- input artifact key contract
- output artifact key contract
- `stage.completed` / `stage.failed` event contract
- MinIO key convention
- job-service ownership of next-stage orchestration

### Input Artifact

Default input:

```text
{object_prefix}/05_export/marker.docx
```

The command may override this with `input_object_key`.

### Output Artifact

Default output:

```text
{object_prefix}/06_hwpx/final.hwpx
```

The command may override this with `output_object_key`.

### Marker Token Policy

The marker token is:

```text
¡
```

The marker pipeline uses `¡` for space restoration. The real custom `pdf2hwpx` library is expected to convert `¡` back to spaces while creating the final HWPX output.

Do not remove the marker stage or change the marker token without a coordinated contract update.

### Suggested Future Configuration

Potential closed-network configuration:

```text
PDF2HWPX_PROVIDER=placeholder
PDF2HWPX_PROVIDER=custom_library
PDF2HWPX_LIBRARY_MODULE=<python module>
PDF2HWPX_TEMP_DIR=/tmp/file-translation/pdf2hwpx-worker
PDF2HWPX_MARKER_TOKEN=¡
```

These flags are not fully implemented today; they document the expected replacement direction.

### Docker Image Build

When the real library is available:

1. add the internal wheel or package source to the build context through the approved closed-network supply path
2. install it in `services/pdf2hwpx-worker/Dockerfile`
3. keep the existing worker entrypoint
4. rebuild `petoo/file-translation-pdf2hwpx-worker:0.1.0` or the deployment-specific tag
5. rerun `scripts/dev/smoke-pdf2hwpx-live.sh`
6. rerun DOCX and PDF route-level E2E smokes

Do not change the frontend/API flow when replacing the library.

Reliability requirement:

- The real custom `pdf2hwpx` library may be long-running for large files.
- The worker runtime now supports job-service stage claim, heartbeat/progress, and lease renewal for job-service-created commands.
- If the worker dies after claim/ack, job-service moves the stage to `retry_pending`, waits until `next_retry_at`, and republishes the retry command only when due.
- Terminal failures must preserve `failed_attempts`, `failed_record`, and `dlq_reason` in job-service state for operator diagnosis.
- The replacement wrapper must preserve this runtime path and add idempotent output finalization before production use if the real library can partially write outputs.
- Do not rely on keeping a RabbitMQ command unacked for the whole conversion.
