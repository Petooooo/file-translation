# Pipeline

Last updated: 2026-06-12 22:08 KST

## Overview

The system supports three input routes:

```text
pdf
docx
hwpx
```

`job-service` chooses the route from `input_type` when the job is created. Workers publish events only; `job-service` decides every next stage.

External clients do not publish RabbitMQ messages. Users, frontends, and admin tools create jobs, cancel jobs, retry jobs, and read results through `job-service` APIs only. RabbitMQ remains internal to `job-service` and workers.

## Common Event Flow

```text
job-service receives job
-> validates input_type
-> stores job metadata and route
-> publishes first stage command
-> worker consumes command
-> worker claims stage through job-service when command_id is present
-> worker acks RabbitMQ after durable claim/no-op
-> worker reads/writes MinIO artifacts
-> worker heartbeats/progresses while work runs
-> worker publishes stage.completed / stage.failed / progress
-> job-service consumes event
-> job-service checks status and cancellation
-> job-service publishes next command or terminal status
```

If a job is `cancel_requested`, `cancelled`, `failed`, `completed`, or `expired`, `job-service` must not publish any new processing stage. `email-worker` must check sendability with `job-service` before sending.

Reliability rule:

- Job-service-created commands include `command_id` and use the claim/early-ack path.
- RabbitMQ ack means durable command acceptance or durable no-op.
- `stage.completed` means actual processing finished.
- Direct legacy commands without `command_id` are developer-smoke compatibility only and are not production-safe.

Detailed plan and implementation status: `docs/RELIABILITY_REPLAN.md`.

## Common Email Send Flow

All routes converge on `email_send` after their final artifacts are available.

```text
job-service publishes q.commands.email_send
-> email-worker consumes command
-> email-worker claims email_send through job-service
-> email-worker queries job-service for job details and sendability
-> email-worker stops without sending if the job is not sendable
-> email-worker resolves final artifact keys from job metadata
-> email-worker downloads or references MinIO artifacts for attachments
-> email-worker calls MailProvider
-> email-worker writes a mock email_report.json in local mode
-> email-worker publishes stage.completed or stage.failed
-> job-service consumes the event and marks the job completed or failed
```

`email-worker` must not be coupled to SMTP. Delivery is provider-based:

- `mock`: default local provider; does not send real mail and should write `reports/email_report.json` to MinIO.
- `smtp`: optional provider only if a deployment needs it.
- `military_api`: later closed-network provider for the internal mail API.

The provider configuration is injected through ConfigMap/Secret/Helm values. No military/internal API URL, header, token, or credential belongs in code.

## PDF Input Route

Route:

```text
PDF input
-> custom pdf2docx static anchored conversion
-> DOCX text parsing using LibreOffice/docx-based parsing
-> translate-worker
-> open DOCX and replace strings using translated JSON
-> save translated DOCX
-> export final PDF
-> open translated DOCX and replace spaces with '¡'
-> save marker DOCX
-> convert marker document through pdf2hwpx stage
-> email final outputs
```

Required converter image:

```text
petoo/pdf2docx:0.5.13-py311-static
```

Allowed floating reference for manual testing only:

```text
petoo/pdf2docx:latest
```

The preferred fixed tag is always `petoo/pdf2docx:0.5.13-py311-static`.

Static anchored CLI:

```bash
python -m pdf2docx.static_anchored.cli \
  --input /work/input.pdf \
  --output /work/output.docx \
  --overwrite
```

Optional report mode:

```bash
python -m pdf2docx.static_anchored.cli \
  --input /work/input.pdf \
  --output /work/output.docx \
  --report /work/output.report.json \
  --markdown-report /work/output.report.md \
  --overwrite
```

Report generation is controlled by config. Do not replace this converter with ordinary upstream `pdf2docx` for the actual PDF route.

Current implementation checkpoint:

- `pdf2docx-worker` is now built from `petoo/pdf2docx:0.5.13-py311-static`.
- Local/container validation is available through `worker.py --convert-local`.
- `worker.py --consume` can consume RabbitMQ commands, download/upload MinIO artifacts, and publish stage events.
- Brokerless/unit validation for command handling and artifact keys is complete.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-pdf2docx-live.sh`.
- Route-level PDF E2E validation is complete through `scripts/dev/smoke-pdf-route-e2e.sh`; it verifies that the custom static anchored `pdf2docx` stage runs before the DOCX-route stages.
- `docx-extract-worker` can consume `docx_extract` commands for both `pdf` and `docx` routes, read the correct DOCX input artifact, write `02_extract/text_units.json`, and publish stage events.
- `translate-worker` can consume `docx_translate` commands for `pdf` and `docx` routes, read `02_extract/text_units.json`, write `03_translate/translated_units.json`, publish `translate.progress`, and publish stage events.
- `docx-replace-worker` can consume `docx_replace` commands for `pdf` and `docx` routes, read the correct original/converted DOCX plus `02_extract/text_units.json` and `03_translate/translated_units.json`, write `04_replace/translated.docx`, and publish stage events.
- The first `docx_replace` MVP updates `word/document.xml` `w:t` nodes using `paragraph_index`, `run_index`, and `text_index` from `text_units.json`. Headers, footers, comments, text boxes, tracked changes, and other DOCX parts are not covered yet.
- `libreoffice-worker` can consume `docx_export` commands for `pdf` and `docx` routes, read `04_replace/translated.docx`, write `05_export/final.docx` and `05_export/final.pdf`, and publish stage events.
- The first `docx_export` MVP uses `DOCX_EXPORT_PDF_MODE=placeholder` by default. It copies the translated DOCX as the final DOCX and writes a valid placeholder PDF until LibreOffice is available in the runtime image.
- The same `libreoffice-worker` image can run `--consume-marker` for `docx_marker`, read `05_export/final.docx`, replace spaces in DOCX text nodes with `¡`, write `05_export/marker.docx`, and publish stage events.
- `pdf2hwpx-worker` can consume `pdf2hwpx` commands for `pdf` and `docx` routes, read `05_export/marker.docx`, write a placeholder `06_hwpx/final.hwpx`, and publish stage events.
- The first `pdf2hwpx` MVP writes a placeholder HWPX zip containing `placeholder.json` and the source marker DOCX. Replace this with the real custom `pdf2hwpx` library when available.

Stages:

```text
receive_input
pdf2docx
docx_extract
docx_translate
docx_replace
docx_export
docx_marker
pdf2hwpx
email_send
completed
```

Expected artifacts:

```text
input/original.pdf
01_pdf2docx/converted.docx
02_extract/text_units.json
03_translate/translated_units.json
04_replace/translated.docx
05_export/final.docx
05_export/final.pdf
05_export/marker.docx
06_hwpx/final.hwpx
reports/pdf2docx.report.json
reports/pdf2docx.report.md
reports/email_report.json
```

The `pdf2hwpx` stage may use a placeholder/stub until the real custom library is available. It is acceptable if `¡` remains in intermediate output. The later real `pdf2hwpx` library converts `¡` back into spaces.

## DOCX Input Route

Route:

```text
DOCX input
-> skip pdf2docx
-> DOCX text parsing
-> translate-worker
-> open DOCX and replace strings using translated JSON
-> save translated DOCX
-> export final PDF
-> open translated DOCX and replace spaces with '¡'
-> save marker DOCX
-> pdf2hwpx stage
-> email final outputs
```

DOCX input must not be converted through `pdf2docx` at the beginning.

Current implementation checkpoint:

- `docx-extract-worker` extracts text from `word/document.xml` in DOCX zip files using the Python standard library.
- The first MVP extracts non-blank `w:t` text nodes from the main document part and records `paragraph_index`, `run_index`, and `text_index`.
- `worker.py --extract-local` validates local/container extraction.
- `worker.py --consume` can consume RabbitMQ `docx_extract` commands, download/upload MinIO artifacts, and publish `stage.completed` or `stage.failed`.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-docx-extract-live.sh`.
- `translate-worker` currently supports a default mock provider and an HTTP provider skeleton for the internal `string` + `uid` API shape.
- `worker.py --translate-local` validates local/container translation.
- `worker.py --consume` can consume RabbitMQ `docx_translate` commands, download/upload MinIO artifacts, publish `translate.progress`, and publish `stage.completed` or `stage.failed`.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-docx-translate-live.sh`.
- `docx-replace-worker` reads the route-specific DOCX input, `02_extract/text_units.json`, and `03_translate/translated_units.json`, then writes `04_replace/translated.docx`.
- `worker.py --replace-local` validates local/container DOCX replacement.
- `worker.py --consume` can consume RabbitMQ `docx_replace` commands, download/upload MinIO artifacts, and publish `stage.completed` or `stage.failed`.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-docx-replace-live.sh`.
- The current replacement MVP is limited to `word/document.xml` text runs. Richer DOCX parts must be added before claiming complete DOCX coverage.
- `libreoffice-worker` reads `04_replace/translated.docx`, writes `05_export/final.docx` and `05_export/final.pdf`, and publishes `stage.completed` or `stage.failed`.
- `worker.py --export-local` validates local/container DOCX export.
- `worker.py --consume` can consume RabbitMQ `docx_export` commands, download/upload MinIO artifacts, and publish stage events.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-docx-export-live.sh`.
- The current PDF output is a placeholder unless `DOCX_EXPORT_PDF_MODE=libreoffice` is enabled in a runtime image that actually contains LibreOffice.
- `worker.py --mark-local` validates local/container marker DOCX generation.
- `worker.py --consume-marker` can consume RabbitMQ `docx_marker` commands, download `05_export/final.docx`, upload `05_export/marker.docx`, and publish stage events.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-docx-marker-live.sh`.
- The marker MVP replaces spaces in `word/*.xml` DOCX text nodes with `¡`. The later real `pdf2hwpx` library is expected to convert `¡` back into spaces.
- `pdf2hwpx-worker` reads `05_export/marker.docx`, writes `06_hwpx/final.hwpx`, and publishes `stage.completed` or `stage.failed`.
- `worker.py --generate-local` validates local/container placeholder HWPX generation.
- `worker.py --consume` can consume RabbitMQ `pdf2hwpx` commands, download/upload MinIO artifacts, and publish stage events.
- Live RabbitMQ and MinIO validation is complete through `scripts/dev/smoke-pdf2hwpx-live.sh`.
- The current output is a placeholder HWPX zip, not a real HWPX conversion.
- `scripts/dev/smoke-docx-route-e2e.sh` validates the route-level DOCX E2E flow from job creation through `email_send` completion.

Stages:

```text
receive_input
docx_extract
docx_translate
docx_replace
docx_export
docx_marker
pdf2hwpx
email_send
completed
```

Expected artifacts:

```text
input/original.docx
02_extract/text_units.json
03_translate/translated_units.json
04_replace/translated.docx
05_export/final.docx
05_export/final.pdf
05_export/marker.docx
06_hwpx/final.hwpx
reports/email_report.json
```

## HWPX Input Route

Route:

```text
HWPX input
-> parse translatable sentence/text units directly with rhwp
-> translate-worker
-> open HWPX with rhwp and replace strings using translated JSON
-> save translated HWPX
-> use LibreOffice H2O-related path to read/export translated HWPX
-> save final PDF and DOCX
-> email final outputs
```

The HWPX route is separate from the DOCX route. Do not force HWPX through PDF/DOCX conversion at the beginning.

Current implementation checkpoint:

- Added `hwpx-worker` for the HWPX direct route.
- `hwpx-worker --consume-extract` can consume `hwpx_extract` commands, read `{object_prefix}/input/original.hwpx`, write `02_extract/text_units.json`, and publish stage events.
- `translate-worker --consume-hwpx` can consume `hwpx_translate` commands and reuse the common translation provider contract to write `03_translate/translated_units.json`.
- `hwpx-worker --consume-replace` can consume `hwpx_replace` commands, read original HWPX plus text/translated units, write `04_replace/translated.hwpx`, and publish stage events.
- `libreoffice-worker --consume-hwpx-export` can consume `hwpx_export` commands, read `04_replace/translated.hwpx`, copy it to `06_hwpx/final.hwpx`, write placeholder `05_export/final.docx` and `05_export/final.pdf`, and publish stage events.
- Local validation is available through `scripts/dev/smoke-hwpx-local.sh`.
- The current HWPX parser/replacer is a deliberate zip/XML stub for local route validation. It is not the final `rhwp` implementation.
- `HWPX_RHWP_ENABLED=false` and `HWPX_H2O_EXPORT_ENABLED=false` are the local defaults.
- `HWPX_H2O_EXPORT_ENABLED=true` is not a working conversion path yet; enabling it fails explicitly until LibreOffice H2O/HWPX support is implemented and validated.

Stages:

```text
receive_input
hwpx_extract
hwpx_translate
hwpx_replace
hwpx_export
email_send
completed
```

Expected artifacts:

```text
input/original.hwpx
02_extract/text_units.json
03_translate/translated_units.json
04_replace/translated.hwpx
05_export/final.docx
05_export/final.pdf
06_hwpx/final.hwpx
reports/email_report.json
```

Validation requirement:

- `rhwp` extraction and replacement must be validated with real sample HWPX files.
- LibreOffice H2O/HWPX read/export must be validated locally or documented as a closed-network dependency.
- Do not assume H2O export works until recorded in `docs/VALIDATION.md`.
- `scripts/dev/smoke-hwpx-live.sh` validates the live MinIO/RabbitMQ contract for `hwpx_extract -> hwpx_translate` with the current local zip/XML stub.
- `scripts/dev/smoke-job-orchestration-live.sh` validates job-service event consumption, PostgreSQL state update, next command publishing, and cancellation gating for the first PDF/DOCX/HWPX transitions.
- `scripts/dev/smoke-hwpx-replace-export-live.sh` validates the worker-backed HWPX route through `hwpx_export`.
- `scripts/dev/smoke-email-end-state-live.sh` validates `email_send` terminal behavior with synthetic upstream events.
- `scripts/dev/smoke-hwpx-route-e2e.sh` validates the route-level HWPX E2E flow from job creation through `email_send` completion.
- `scripts/dev/smoke-docx-route-e2e.sh` validates the route-level DOCX E2E flow from job creation through `docx_marker`, `pdf2hwpx`, and `email_send` completion.
- `scripts/dev/smoke-pdf-route-e2e.sh` validates the route-level PDF E2E flow from job creation through the custom static anchored `pdf2docx` stage, DOCX-route stages, `pdf2hwpx`, and `email_send` completion.

## Output Expectations By Route

| input_type | final_docx_key | final_pdf_key | final_hwpx_key | translated_hwpx_key |
| --- | --- | --- | --- | --- |
| `pdf` | Required | Required | Required or placeholder | Usually not applicable |
| `docx` | Required | Required | Required or placeholder | Usually not applicable |
| `hwpx` | Required if H2O export works | Required if H2O export works | Original/final HWPX output | Required |

If a route cannot produce a target artifact because a local dependency is unavailable, `job-service` should mark the stage failed with a clear `error_stage` and `error_message`.

Every completed route should also produce `reports/email_report.json` when `EMAIL_PROVIDER=mock`. Real providers may still write the same report for audit/debug consistency, but the report must not contain secrets.
