# File Translation MSA Project Plan

Last updated: 2026-06-09 23:52 KST

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
- Git branch: `codex/plan-bootstrap-local-k8s`
- Base branch: `main`
- Initial docs commits: `4dd9149`, `850d0bb`
- Remote: `git@github.com:Petooooo/file-translation.git`
- Existing project files: Markdown docs and Phase 1 local dev scripts

Initial planning docs were committed on `main` because the repository was empty. Phase 1 and later implementation work should use task branches.

## Phase Plan

| Phase | Status | Purpose | Exit Criteria |
| --- | --- | --- | --- |
| 0. Repository and Environment Inspection | Completed | Inspect repo, Git state, local tooling, and create initial docs. | Initial docs committed with inspection results and validation log. |
| 1. Local Cluster Bootstrap Plan | Completed on this PC | Choose k3d/kind/k3s path and document repeatable local bootstrap. | Scripts exist, Helm/k3d are installed in `~/.local/bin`, k3d cluster is reachable, namespace and DNS smoke test passed. |
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

## Local Cluster State

The previous local tooling blocker is resolved on this PC.

- Helm: `v4.2.0`, installed in `~/.local/bin`
- k3d: `v5.9.0`, installed in `~/.local/bin`
- Local context: `k3d-file-translation-dev`
- Local Kubernetes: k3s `v1.32.13+k3s1`
- Namespace: `file-translation`

Revalidation command sequence:

```bash
scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
```

## Next Recommended Step

Begin Phase 2 by creating minimal service and worker skeletons.
