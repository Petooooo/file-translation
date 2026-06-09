# File Translation MSA Project Plan

Last updated: 2026-06-09 20:12 KST

## Goal

Build a portable local Kubernetes development environment and MSA pipeline for a file translation system that can later run in an air-gapped Kubernetes environment.

The target runtime uses:

- Kubernetes, likely k3s around v1.32 in the closed network
- MinIO around 2025-02 for original, intermediate, and final artifacts
- RabbitMQ for worker commands and pipeline events
- PostgreSQL for job metadata and stage state
- Internal translation API in production
- Helm as the deployment interface

All project state needed for continuation must be recorded in repository files, especially Markdown docs.

## Current Repository State

- Repository path: `/mnt/c/Workspace/Codex/file-translation`
- Git branch: `main`
- Commit state: no commits yet
- Remote: `git@github.com:Petooooo/file-translation.git`
- Existing project files: none outside `.git`

Because the repository has no commits yet, initial planning docs may be committed on `main`. Future implementation work should use task branches.

## Phase Plan

| Phase | Status | Purpose | Exit Criteria |
| --- | --- | --- | --- |
| 0. Repository and Environment Inspection | In progress | Inspect repo, Git state, local tooling, and create initial docs. | Initial docs committed with inspection results and validation log. |
| 1. Local Cluster Bootstrap Plan | Pending | Choose k3d/kind/k3s path and document repeatable local bootstrap. | Scripts and docs can create or clearly block local cluster setup. |
| 2. Skeleton Services | Pending | Create minimal service and worker skeletons. | Each service has config, logging, Dockerfile, and basic test or smoke command. |
| 3. RabbitMQ + Job Orchestration | Pending | Implement command/event flow with job-service as orchestrator. | Workers publish events only; job-service publishes next commands. |
| 4. MinIO Artifact Flow | Pending | Implement bucket/key convention and artifact read/write helpers. | Tests verify expected object keys and artifact flow. |
| 5. Document Pipeline | Pending | Add placeholder PDF/DOCX/HWPX processing flow. | Pipeline can produce placeholder final artifacts locally. |
| 6. Helm Chart | Pending | Add `charts/file-translation` with local and closed-network values. | Helm templates validate and deploy locally when cluster is available. |
| 7. End-to-End Smoke Test | Pending | Verify submit, process, complete, cancel, and fail paths. | Smoke test results recorded in `docs/VALIDATION.md`. |

## Implementation Principles

- `job-service` owns PostgreSQL schema and pipeline orchestration.
- Workers are stateless and stage-specific.
- Workers consume only their command queues and publish events back to RabbitMQ.
- Workers must not publish commands for the next stage.
- MinIO stores all file artifacts using the required object key convention.
- Job cancellation is state control, not immediate MinIO deletion.
- Environment-specific values must be ConfigMap or Secret driven.
- No closed-network IPs, credentials, tokens, or URLs may be hard-coded.
- Docker images use explicit version tags under Docker Hub namespace `petoo`.
- Do not push Git commits unless explicitly requested.

## Planned Branches

Use `codex/` prefix for branches unless the user requests otherwise.

- `codex/plan-bootstrap-local-k8s`
- `codex/feat-skeleton-services`
- `codex/feat-rabbitmq-orchestration`
- `codex/feat-minio-artifacts`
- `codex/feat-helm-chart`
- `codex/test-e2e-smoke`

## Next Recommended Step

Finish Phase 0 by committing these initial planning docs. Then begin Phase 1 by creating a task branch, adding environment check and bootstrap scripts, and validating the chosen local cluster path.

