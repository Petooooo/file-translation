# Pipeline

Last updated: 2026-06-10 12:35 KST

## Overview

The system supports three input routes:

```text
pdf
docx
hwpx
```

`job-service` chooses the route from `input_type` when the job is created. Workers publish events only; `job-service` decides every next stage.

## Common Event Flow

```text
job-service receives job
-> validates input_type
-> stores job metadata and route
-> publishes first stage command
-> worker consumes command
-> worker reads/writes MinIO artifacts
-> worker publishes stage.completed / stage.failed / progress
-> job-service consumes event
-> job-service checks status and cancellation
-> job-service publishes next command or terminal status
```

If a job is `cancel_requested`, `cancelled`, `failed`, `completed`, or `expired`, `job-service` must not publish any new processing stage. `email-worker` must check sendability with `job-service` before sending.

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
```

Validation requirement:

- `rhwp` extraction and replacement must be validated with real sample HWPX files.
- LibreOffice H2O/HWPX read/export must be validated locally or documented as a closed-network dependency.
- Do not assume H2O export works until recorded in `docs/VALIDATION.md`.

## Output Expectations By Route

| input_type | final_docx_key | final_pdf_key | final_hwpx_key | translated_hwpx_key |
| --- | --- | --- | --- | --- |
| `pdf` | Required | Required | Required or placeholder | Usually not applicable |
| `docx` | Required | Required | Required or placeholder | Usually not applicable |
| `hwpx` | Required if H2O export works | Required if H2O export works | Original/final HWPX output | Required |

If a route cannot produce a target artifact because a local dependency is unavailable, `job-service` should mark the stage failed with a clear `error_stage` and `error_message`.
