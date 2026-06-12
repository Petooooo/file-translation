# File Translation MSA Project Plan

Last updated: 2026-06-12 09:00 KST

## Goal

Build a portable local Kubernetes development environment and MSA pipeline for a file translation system that supports three input types:

```text
pdf
docx
hwpx
```

The target runtime remains an air-gapped Kubernetes environment with MinIO, RabbitMQ, PostgreSQL, an internal translation API, and Helm-based deployment.

All continuation-critical state must be recorded in committed Markdown docs and repository files.

## Current Repository State

- Repository path: `/mnt/d/workspaces/codex/file-translation`
- Current branch: `test/pdf-route-e2e-smoke`
- Current checkpoint: HWPX, DOCX, and PDF route-level E2E smokes are complete; public job-service API boundary and operation/replacement/closed-network guide requirements are recorded; see `docs/PIPELINE.md`, `docs/CONTRACTS.md`, `docs/API.md`, `docs/USAGE.md`, `docs/VALIDATION.md`, and `docs/PROGRESS.md`
- Replan base: `716f361` from `docs/pipeline-replan`
- Useful work preserved:
  - Phase 1 local k3d/k3s bootstrap scripts
  - Phase 2 Python service skeletons and image build scripts
  - existing validation, troubleshooting, and image inventory records
- Remote: `git@github.com:Petooooo/file-translation.git`

Do not restart the repository from scratch. Existing setup and skeleton work should be adapted to the revised multi-input plan.

## Revised Phase Plan

| Phase | Status | Purpose | Exit Criteria |
| --- | --- | --- | --- |
| 0. Repository and Environment Inspection | Completed | Inspect repo, Git state, local tooling, and create initial docs. | Initial docs committed with inspection results and validation log. |
| 1. Local Cluster Bootstrap Plan | Completed and revalidated | Keep reproducible local k3d/k3s setup. | Existing k3d cluster and namespace are reachable; DNS smoke passes. |
| 2. Skeleton Services | Completed previously; requires route alignment later | Minimal service/worker skeletons. | Existing skeletons preserved; future branches must adapt stages to `pdf`, `docx`, and `hwpx` routes. |
| 3. Pipeline Replan | Completed | Revise docs/contracts for PDF, DOCX, and HWPX inputs. | `PIPELINE.md`, `CONTRACTS.md`, architecture, plan, decisions, validation, and troubleshooting updated. |
| 4. job-service Input Routing | Completed | Implement `input_type` routing, job metadata, stage model, and event-driven next-stage decisions. | `job-service` creates jobs for `pdf`, `docx`, `hwpx` and publishes only the correct initial command. |
| 4.1 RabbitMQ Orchestration Adapters | Completed and live-smoked | Add RabbitMQ command publisher and event consumer adapters behind job-service interfaces. | Unit tests cover queue mapping; live smoke verifies RabbitMQ event consumption, PostgreSQL state update, next command publish, and cancellation gate. |
| 5. PDF/DOCX Pipeline | PDF and DOCX route E2E live-smoked | Implement PDF route using custom static anchored pdf2docx image and DOCX route without initial PDF conversion. | PDF and DOCX jobs reach terminal `completed` through MinIO/RabbitMQ/PostgreSQL/job-service/workers/email-worker. |
| 6. HWPX rhwp Pipeline | Placeholder route E2E live-smoked | Implement direct HWPX parse/replace with `rhwp` and validate LibreOffice H2O read/export path. | Placeholder HWPX jobs now reach terminal `completed` through MinIO/RabbitMQ/PostgreSQL/job-service/workers/email-worker; real `rhwp` and H2O remain pending. |
| 7. End-to-End Smoke Tests | HWPX, DOCX, and PDF E2E completed | Verify all input routes and cancellation/failure behavior. | All three route E2E smokes record final artifacts, email reports, RabbitMQ drain, PostgreSQL terminal state, and cancellation gates. |
| 8. Operation/API/Admin/Replacement Docs | Completed | Record public API boundary, user/admin usage, closed-network integration, external RabbitMQ, email provider replacement, and pdf2hwpx replacement requirements before Helm. | Frontend/admin/user clients are documented as job-service-only clients; RabbitMQ remains internal; replacement points are documented without implementing Helm. |
| 9. Helm Local Stack | Pending | Add Helm chart with local and closed-network values and external dependency support. | `charts/file-translation` deploys services and optionally bundled dependencies. |

## Required Architecture Updates

- `job-service` determines initial stage from `input_type`.
- `job-service` is the only public job API for frontend, admin UI, and users.
- Frontend, admin UI, and users must not publish RabbitMQ messages.
- Workers still never enqueue the next worker directly.
- Pipeline routes are branch-specific but event handling is common.
- Object keys use `{YYYY-MM-DD}/{user_id}/{file_id}/...`.
- PDF input uses `petoo/pdf2docx:0.5.13-py311-static` or a worker image based on it.
- DOCX input skips initial `pdf2docx`.
- HWPX input uses a separate `rhwp` path and must not be forced through PDF/DOCX conversion at the beginning.
- LibreOffice H2O/HWPX read/export is a validation item, not an assumption.
- `email-worker` remains a stage worker, but mail delivery must be behind a `MailProvider` adapter.
- Local development defaults to `EMAIL_PROVIDER=mock`; closed-network deployments may use `EMAIL_PROVIDER=military_api`.
- Mail API URLs, credentials, tokens, headers, and timeouts must be injected through ConfigMap/Secret/Helm values, never hard-coded.

## Branch Strategy

Use these branches for parallel work. Avoid editing shared contracts from feature branches unless absolutely necessary.

| Branch | Owns | Avoids |
| --- | --- | --- |
| `docs/pipeline-replan` | Docs, contracts, route/stage definitions, branch ownership plan. | Runtime implementation beyond tiny contract alignment. |
| `docs/email-provider-contract` | Email provider strategy, mail command/event/report contracts, and Helm value shape. | Runtime email-provider implementation. |
| `feat/job-service-input-routing` | `job-service`, PostgreSQL schema/migrations, route selection, cancellation gates, event consumer. | Worker conversion logic and Helm dependency charts. |
| `feat/rabbitmq-orchestration` | RabbitMQ command publisher/event consumer adapters and orchestration wiring. | Worker conversion logic, PostgreSQL persistence, and Helm dependency charts. |
| `feat/pdf-docx-pipeline` | DOCX parsing/replacement/export path and marker DOCX handling. | HWPX `rhwp` internals and shared contracts. |
| `feat/email-worker-provider` | `email-worker` provider interface, local mock provider, sendability gate, and email report artifact flow. | PDF/DOCX/HWPX conversion internals and shared contract changes. |
| `feat/pdf2docx-static-worker` | `pdf2docx-worker` image/runtime using `petoo/pdf2docx:0.5.13-py311-static`, optional reports. | Generic DOCX/HWPX processing. |
| `feat/hwpx-rhwp-pipeline` | HWPX extract/replace/export path, `rhwp`, LibreOffice H2O validation. | PDF/DOCX worker logic. |
| `feat/helm-local-stack` | `charts/file-translation`, local values, closed-network example values, dependency toggles. | Pipeline business logic. |
| `test/e2e-pipeline-smoke` | End-to-end smoke tests, sample inputs, route-level validation. | Contract changes unless coordinated through docs branch. |

Rules:

- Do not push Git unless explicitly requested.
- Commit every meaningful unit of work.
- Record commit hashes in `docs/PROGRESS.md`.
- If a feature branch needs to change `docs/CONTRACTS.md` or `docs/PIPELINE.md`, stop and report first.

## Local Cluster State

Previous useful state:

- Helm `v4.2.0` installed in `~/.local/bin`
- k3d `v5.9.0` installed in `~/.local/bin`
- k3d cluster name `file-translation-dev`
- intended local context `k3d-file-translation-dev`
- intended namespace `file-translation`
- intended k3s image `rancher/k3s:v1.32.13-k3s1`

Current session note:

- `scripts/dev/check-env.sh` passes in the current session.
- Existing k3d cluster `file-translation-dev` is reachable.
- Do not recreate the cluster blindly; revalidate with `scripts/dev/check-env.sh` and `scripts/dev/smoke-test.sh` first.

## Next Recommended Step

Route-level HWPX, DOCX, and PDF E2E smoke coverage is now in place, and operation/API/admin/replacement/closed-network requirements are recorded. The next larger project task is `feat/helm-local-stack` so the expanded service set can be deployed through Helm without exposing RabbitMQ to frontend/admin/user clients.
