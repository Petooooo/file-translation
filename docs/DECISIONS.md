# Decisions

Last updated: 2026-06-12 21:25 KST

## ADR-0001: Use Documentation-Driven Continuation

Status: Accepted

Decision:

- Keep project plan, architecture, setup, progress, validation, decisions, and troubleshooting in committed Markdown files.
- Future sessions must read these docs first when asked to continue from recorded state.

Reason:

- The project must be portable across PCs and future Codex sessions.
- Continuation must not depend on conversational memory.

## ADR-0002: Allow Initial Planning Commit on main

Status: Accepted

Decision:

- Commit initial planning docs on `main`.
- Use task branches after the first commit.

Reason:

- The repository has no commits and contains no project files.
- The user explicitly allowed direct `main` work for empty-repo initial docs.

## ADR-0003: Prefer k3d for Local Kubernetes

Status: Accepted

Decision:

- Prefer k3d for local development if it can be installed and started successfully.
- Use kind as fallback.

Reason:

- The closed-network target is likely k3s.
- k3d runs k3s in Docker and should be closer to the target environment than kind.
- Docker and kubectl are already available on this PC.

Alternatives:

- Native k3s: closer to production, but usually more intrusive on a developer PC.
- kind: easy and reproducible, but not k3s.

## ADR-0004: job-service Owns Orchestration

Status: Accepted

Decision:

- Workers publish stage events only.
- `job-service` consumes events, checks PostgreSQL state and cancellation, and publishes the next command.

Reason:

- Centralized orchestration keeps stage ordering, cancellation, and job status consistent.
- Workers remain stateless and replaceable.

## ADR-0005: Cancellation Does Not Delete MinIO Artifacts Immediately

Status: Accepted

Decision:

- Cancellation is represented by job state.
- Already written artifacts stay in MinIO until lifecycle/ILM deletion.

Reason:

- This keeps cancellation simple and reliable.
- Closed-network MinIO lifecycle policy can handle retention and cleanup.

## ADR-0006: Start Without Outbox, Document Upgrade Path

Status: Proposed

Decision:

- The MVP may publish RabbitMQ messages directly from `job-service`.
- Add an outbox table later if reliability testing shows a need.

Reason:

- A direct publisher is faster for the first working pipeline.
- The PostgreSQL schema plan reserves an outbox upgrade path.

## ADR-0007: Do Not Auto-Install Host Tools From Project Scripts

Status: Accepted

Decision:

- Project scripts check for Docker, kubectl, Helm, k3d, and optional fallback tools.
- Project scripts prepend `~/.local/bin` to PATH when it exists.
- Scripts print exact install commands when tools are missing.
- Scripts do not run host-level install commands automatically.

Reason:

- Host tool installation can require privileges, change user machines, and block on interactive prompts.
- The project must remain portable and explicit across different PCs.

## ADR-0008: Support kind as an Explicit Fallback

Status: Accepted

Decision:

- `scripts/dev/bootstrap-cluster.sh` defaults to k3d.
- `CLUSTER_PROVIDER=kind` creates or reuses a kind cluster when k3d cannot be used.

Reason:

- k3d remains closest to the expected k3s target.
- kind keeps the project unblocked on PCs where k3d is not available but Docker-based Kubernetes is acceptable for early development.

## ADR-0009: Pin Local k3d Cluster to k3s v1.32

Status: Accepted

Decision:

- `scripts/dev/bootstrap-cluster.sh` defaults `K3D_IMAGE` to `rancher/k3s:v1.32.13-k3s1`.
- Users can override the image with `K3D_IMAGE=...` when another version is needed.

Reason:

- The expected closed-network target is likely around k3s v1.32.
- k3d v5.9.0 defaults to a newer k3s line, so pinning keeps local development closer to the target.

## ADR-0010: Use Python Standard Library for Phase 2 Skeletons

Status: Accepted

Decision:

- Build Phase 2 service skeletons with Python 3 and the standard library only.
- Defer FastAPI, RabbitMQ clients, PostgreSQL clients, and MinIO SDK dependencies until their integration phases.

Reason:

- The repository needs runnable skeletons before infrastructure integration.
- Avoiding third-party packages keeps early validation independent of external package registries.
- The skeleton still preserves service boundaries, Dockerfiles, env-driven config, health checks, and structured logs.

## ADR-0011: Support pdf, docx, and hwpx Inputs

Status: Accepted

Decision:

- `input_type` is required and must be one of `pdf`, `docx`, or `hwpx`.
- `job-service` routes each job to the initial stage for that input type.

Reason:

- The project is no longer PDF-only.
- Explicit input routing keeps PDF, DOCX, and HWPX behavior testable and prevents accidental conversion through the wrong path.

## ADR-0012: Use YYYY-MM-DD MinIO Prefixes

Status: Accepted

Decision:

- Object prefixes use `{YYYY-MM-DD}/{user_id}/{file_id}`.
- The previous `{yy-mm-dd}` format is obsolete.

Reason:

- Full-year prefixes are clearer, sort correctly over long retention periods, and match the revised contract.

## ADR-0013: Use Static Anchored pdf2docx Image for PDF Route

Status: Accepted

Decision:

- PDF input conversion uses `petoo/pdf2docx:0.5.13-py311-static` or a worker image based on it.
- The CLI is `python -m pdf2docx.static_anchored.cli`.
- Ordinary upstream `pdf2docx` must not replace this converter for the actual PDF route.

Reason:

- The image contains the custom static anchored converter with improved header/footer handling.

## ADR-0014: Keep HWPX as a Separate rhwp Route

Status: Accepted

Decision:

- HWPX input starts with direct `rhwp` extraction.
- HWPX input must not be forced through initial PDF/DOCX conversion.
- LibreOffice H2O/HWPX read/export is a validation item.

Reason:

- HWPX has its own document structure and replacement requirements.
- Treating H2O support as unvalidated prevents false confidence in local and closed-network deployments.

## ADR-0015: Freeze Shared Contracts Before Parallel Feature Work

Status: Accepted

Decision:

- `docs/pipeline-replan` owns shared route, stage, message, and artifact contracts.
- Feature branches should not edit `docs/PIPELINE.md` or `docs/CONTRACTS.md` unless they stop and report first.

Reason:

- Multiple PCs and Codex sessions may work in parallel.
- Contract drift across branches would make RabbitMQ, MinIO, PostgreSQL, and Helm work conflict-prone.

## ADR-0016: Put RabbitMQ Behind job-service Interfaces First

Status: Accepted

Decision:

- Keep `job-service` command publishing behind a `CommandPublisher` interface.
- Use `JOB_SERVICE_COMMAND_PUBLISHER=memory` by default for local unit tests and smoke commands.
- Enable real RabbitMQ command publishing with `JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq`.
- Keep event consumption disabled by default and enable it with `JOB_SERVICE_EVENT_CONSUMER=rabbitmq`.
- Add `pika` only to the `job-service` container runtime for the RabbitMQ adapter.

Reason:

- The project still needs fast host-side tests that do not require a running broker.
- The same orchestration code can run against in-memory tests or RabbitMQ with no worker routing changes.
- Deferring PostgreSQL/outbox persistence keeps this branch focused while preserving a clear upgrade path.

## ADR-0017: Base pdf2docx-worker on the Static Anchored Image

Status: Accepted

Decision:

- Build `pdf2docx-worker` from `petoo/pdf2docx:0.5.13-py311-static`.
- Invoke the converter through `python -m pdf2docx.static_anchored.cli`.
- Keep host-side tests independent of the converter package by testing command construction and using a fake runner.
- Provide `--convert-local` for local/container validation before RabbitMQ and MinIO worker integration.

Reason:

- The PDF route must use the custom static anchored converter, not ordinary upstream `pdf2docx`.
- Using the custom image as the worker base guarantees the expected CLI is present in the runtime image.
- The fake-runner test boundary keeps normal unit tests quick while Docker smoke tests verify the real converter.

## ADR-0018: Add Brokerless Worker IO Tests Before Live Stack Tests

Status: Accepted

Decision:

- Add common MinIO and RabbitMQ helper modules in `ft_common`.
- Cover worker artifact key calculation, MinIO operations, RabbitMQ JSON publish/consume, and event payloads with fake clients first.
- Keep live MinIO/RabbitMQ validation as a separate smoke test once the local stack is deployed.

Reason:

- The worker must be testable on PCs where RabbitMQ or MinIO are not currently running.
- Fake-client tests protect the core command/artifact/event contracts.
- Live stack tests can then focus on infrastructure wiring rather than basic message shape bugs.

## ADR-0019: Use Standard-Library DOCX XML Extraction for the First MVP

Status: Accepted

Decision:

- Implement the first `docx_extract` worker with Python `zipfile` and `xml.etree.ElementTree`.
- Extract non-blank `w:t` nodes from `word/document.xml`.
- Record `paragraph_index`, `run_index`, and `text_index` in each text unit location.
- Defer richer DOCX coverage, such as headers, footers, tables beyond main document traversal edge cases, comments, and tracked changes, until replacement requirements are proven.

Reason:

- The project needs a small, dependency-light `text_units.json` producer before translation and replacement stages can be validated.
- Standard-library extraction keeps local tests fast and portable across PCs.
- The location model gives the later replacement worker a concrete starting point without committing to a heavy DOCX abstraction too early.

## ADR-0020: Default translate-worker to a Mock Provider

Status: Accepted

Decision:

- Keep translation logic behind a provider interface.
- Use `TRANSLATION_PROVIDER=mock` by default for local development and smoke tests.
- Add an HTTP provider skeleton for the internal API shape where the request contains `string` and `uid`, and the response contains a translated result string.
- Do not require paid API keys or external translation services for local validation.

Reason:

- Local development does not have the real closed-network translation API.
- The mock provider makes the pipeline deterministic and portable across PCs.
- The HTTP provider boundary lets the real internal API be wired later without changing worker artifact/event contracts.

## ADR-0021: Use text_units Locations for DOCX Replacement MVP

Status: Accepted

Decision:

- `docx-replace-worker` reads both `text_units.json` and `translated_units.json`.
- `translated_units.json` remains translation-focused and maps translations by `uid`.
- Replacement location metadata stays in `text_units.json`.
- The first MVP replaces `word/document.xml` `w:t` nodes using `paragraph_index`, `run_index`, and `text_index`.
- Richer DOCX parts such as headers, footers, comments, text boxes, and tracked changes are deferred.

Reason:

- Keeping location metadata in `text_units.json` avoids duplicating document structure in `translated_units.json`.
- The extraction and replacement workers can share a concrete location contract while the translation worker remains document-format agnostic.
- A standard-library implementation is enough to validate the RabbitMQ/MinIO artifact flow before adding a heavier DOCX abstraction.

## ADR-0022: Use Placeholder PDF for docx_export Until LibreOffice Runtime Is Ready

Status: Accepted

Decision:

- `libreoffice-worker` implements `docx_export` artifact/event flow before installing LibreOffice in the runtime image.
- The local default is `DOCX_EXPORT_PDF_MODE=placeholder`.
- In placeholder mode, the worker copies `04_replace/translated.docx` to `05_export/final.docx` and writes a small valid placeholder PDF to `05_export/final.pdf`.
- `DOCX_EXPORT_PDF_MODE=libreoffice` is available as a future path and requires a runtime image with a working LibreOffice binary.

Reason:

- The branch goal is to validate orchestration and artifact movement stage by stage without blocking on a heavier office runtime.
- The placeholder PDF makes downstream artifact contracts testable in local Docker and future Kubernetes smoke tests.
- Explicit mode selection prevents mistaking the placeholder for a real document conversion.

## ADR-0023: Run docx_marker From the libreoffice-worker Image

Status: Accepted

Decision:

- Use the existing `libreoffice-worker` image for the `docx_marker` stage.
- Keep `--consume` as the `docx_export` consumer and add `--consume-marker` for the `docx_marker` queue.
- `docx_marker` reads `05_export/final.docx`, replaces spaces in DOCX text nodes with `¡`, and writes `05_export/marker.docx`.

Reason:

- The current service inventory does not include a separate `docx-marker-worker`.
- Reusing the same image keeps local development and later Helm deployment smaller while preserving a separate RabbitMQ queue and stage contract.
- The marker operation is a DOCX post-processing step adjacent to export and does not require direct access to translation internals.

## ADR-0024: Use Placeholder HWPX Package for pdf2hwpx MVP

Status: Accepted

Decision:

- Implement `pdf2hwpx-worker` artifact/event flow before the real custom `pdf2hwpx` library is available.
- The MVP reads `05_export/marker.docx` and writes `06_hwpx/final.hwpx`.
- The output is a placeholder zip package containing `placeholder.json` and `source/marker.docx`.
- The completed event uses `final_hwpx` so `job-service` can update final artifact metadata.

Reason:

- The pipeline needs a stable artifact and RabbitMQ contract before real HWPX conversion is integrated.
- Keeping the source marker DOCX inside the placeholder package makes smoke tests deterministic and debuggable.
- Explicit placeholder metadata prevents confusing the MVP artifact with a real HWPX conversion.

## ADR-0025: Use a Pluggable MailProvider for email-worker

Status: Accepted

Decision:

- Keep `email-worker` as the `email_send` stage worker.
- Put actual delivery behind a `MailProvider` interface.
- Use `EMAIL_PROVIDER=mock` by default for local development.
- Allow optional `smtp` and later `military_api` provider adapters without changing the stage contract.
- Inject provider URL, timeout, sender, headers, tokens, and credentials through ConfigMap/Secret/Helm values.
- Require `email-worker` to call `job-service` sendability before any provider call.

Reason:

- The closed-network target is expected to use a military/internal mail API, not necessarily SMTP.
- Local development must not send real email by default.
- A provider adapter keeps the email stage replaceable while preserving RabbitMQ events, MinIO artifacts, and job-service orchestration.
- Keeping credentials out of code is required for both local portability and closed-network deployment.

## ADR-0026: Add HWPX Route Skeleton With Explicit Local Stub

Status: Accepted

Decision:

- Add a dedicated `hwpx-worker` service for `hwpx_extract` and `hwpx_replace`.
- Reuse `translate-worker` for `hwpx_translate` through a separate `--consume-hwpx` mode and `q.commands.hwpx_translate`.
- Reuse `libreoffice-worker` for `hwpx_export` through a separate `--consume-hwpx-export` mode and `q.commands.hwpx_export`.
- Keep local HWPX parsing/replacement as a small zip/XML stub until the real `rhwp` library is available.
- Keep local HWPX export as a placeholder path until LibreOffice H2O/HWPX read/export support is validated.
- Add explicit config flags `HWPX_RHWP_ENABLED` and `HWPX_H2O_EXPORT_ENABLED`, both defaulting to `false`.

Reason:

- The project needs the HWPX RabbitMQ/MinIO artifact route to be testable before the closed-network document libraries are available.
- A dedicated worker preserves the requirement that HWPX input must not be forced through the DOCX/PDF route.
- Placeholder export and explicit failure for unimplemented H2O mode prevent the local MVP from pretending real HWPX-to-DOCX/PDF conversion is complete.
- The route can later swap the internal implementation to `rhwp` without changing job-service orchestration, queue names, or object key contracts.

## ADR-0027: Use a JSONB PostgreSQL Repository for Orchestration Live Smoke

Status: Accepted

Decision:

- Keep `JOB_SERVICE_REPOSITORY=memory` as the default for unit tests and lightweight service smoke.
- Add `JOB_SERVICE_REPOSITORY=postgres` for live orchestration smoke.
- Store the full job aggregate as JSONB in a `jobs` table for the first PostgreSQL-backed validation.
- Keep normalized `job_stages` and outbox tables as future work.

Reason:

- The immediate goal is to verify that `job-service` consumes worker events, checks job/cancel state, persists state, and publishes the next RabbitMQ command.
- A JSONB aggregate avoids a premature schema redesign while making PostgreSQL state updates observable in live smoke.
- The repository boundary keeps worker contracts unchanged and preserves the path to a normalized schema later.

## ADR-0028: Replan Long-Running Stage Reliability Before Helm

Status: Accepted

Decision:

- Do not proceed directly from route-level E2E smoke and Admin API readiness to Helm/local-stack.
- First implement a reliability upgrade for long-running stages.
- Treat RabbitMQ command ack as durable command acceptance or durable no-op, not as actual processing completion.
- Keep actual processing completion represented by `stage.completed`.
- Add job-service-owned stage claim, lease, heartbeat/progress, idempotency, bounded retry/backoff, and duplicate email-send prevention before Helm work resumes.

Reason:

- Large PDF/HWPX/DOCX files can make `pdf2docx`, `pdf2hwpx`, `docx_export`, and `hwpx_export` run long enough to risk RabbitMQ heartbeat timeout, connection loss, unacked redelivery, duplicate stage execution, and duplicate email sends.
- The current architecture already makes `job-service` and PostgreSQL the source of truth; reliability state belongs there rather than in frontend/admin tooling or worker-to-worker queue publishing.
- Helm would make the current behavior easier to deploy but would not fix the at-least-once delivery and idempotency risks.

Plan:

- Use `docs/RELIABILITY_REPLAN.md` as the implementation guide.
- Keep RabbitMQ internal to job-service/workers.
- Keep workers publishing events only; `job-service` remains the only component that publishes next-stage commands.
