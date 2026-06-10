# Decisions

Last updated: 2026-06-10 12:35 KST

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
