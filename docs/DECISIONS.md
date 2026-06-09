# Decisions

Last updated: 2026-06-09 20:12 KST

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

Status: Proposed

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

