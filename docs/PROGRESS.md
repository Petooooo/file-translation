# Progress Log

## 2026-06-09 20:12 KST - Phase 0 inspection and planning docs

Done:

- Inspected repository structure.
- Confirmed repository has no commits and no project files outside `.git`.
- Confirmed current branch is `main`.
- Confirmed remote `origin` is `git@github.com:Petooooo/file-translation.git`.
- Checked local tooling availability.
- Started initial Markdown documentation set.

Verified:

- Docker is installed and server is reachable.
- Docker Compose is installed.
- kubectl is installed.
- Helm, k3s, k3d, and kind are not installed.
- kubectl context `docker-desktop` exists, but Kubernetes API is not reachable.

Commit:

- Initial planning docs committed as `4dd9149` with message `docs: add initial project plan`.

Next recommended step:

- Begin Phase 1 on a task branch by adding environment check and cluster bootstrap scripts.

## 2026-06-09 22:06 KST - Phase 1 local bootstrap scripts

Done:

- Created branch `codex/plan-bootstrap-local-k8s`.
- Added `scripts/dev/check-env.sh`.
- Added `scripts/dev/bootstrap-cluster.sh`.
- Added `scripts/dev/smoke-test.sh`.
- Confirmed k3d is the default local cluster path with kind as explicit fallback.
- Updated setup, validation, troubleshooting, and decision docs.

Verified:

- Bash syntax validation passed for all three scripts.
- Script help output works for bootstrap and smoke-test scripts.
- `check-env.sh` correctly reports Docker/kubectl available and Helm/k3d missing.
- `bootstrap-cluster.sh` correctly blocks because k3d is missing.
- `smoke-test.sh` correctly blocks because the current Kubernetes API is not reachable.

Commit:

- Phase 1 scripts/docs committed as `eee64a0` with message `chore: add local cluster bootstrap scripts`.

Next recommended step:

- Install Helm and k3d, then run `scripts/dev/check-env.sh`, `scripts/dev/bootstrap-cluster.sh`, and `scripts/dev/smoke-test.sh`.

## 2026-06-09 23:52 KST - Phase 1 blocker resolved

Done:

- Installed Helm `v4.2.0` into `/home/peto/.local/bin`.
- Installed k3d `v5.9.0` into `/home/peto/.local/bin`.
- Updated scripts to prepend `~/.local/bin` to PATH when available.
- Updated k3d bootstrap default image to `rancher/k3s:v1.32.13-k3s1`.
- Created local k3d cluster `file-translation-dev`.
- Created namespace `file-translation`.

Verified:

- `scripts/dev/check-env.sh` passes.
- `scripts/dev/bootstrap-cluster.sh` passes.
- `scripts/dev/smoke-test.sh` passes.
- Current context is `k3d-file-translation-dev`.
- Cluster nodes are Ready on k3s `v1.32.13+k3s1`.
- CoreDNS resolved `kubernetes.default.svc.cluster.local` from a busybox pod.

Commit:

- Blocker-resolution work committed as `5e52784` with message `chore: resolve local cluster bootstrap blocker`.

Next recommended step:

- Begin Phase 2 by creating skeleton services.

## 2026-06-10 00:31 KST - Phase 2 skeleton plan

Done:

- Fast-forwarded local `main` to include completed Phase 1 commits.
- Created branch `codex/feat-skeleton-services`.
- Added `docs/PHASE_2_SKELETON_PLAN.md`.
- Updated `docs/PROJECT_PLAN.md` to mark Phase 2 as in progress.

Verified:

- `scripts/dev/check-env.sh` passes against the local k3d cluster.

Commit:

- Phase 2 plan committed as `27f9f02` with message `docs: plan skeleton services phase`.

Next recommended step:

- Implement skeleton services according to `docs/PHASE_2_SKELETON_PLAN.md`.

## 2026-06-10 01:16 KST - Phase 2 skeleton services

Done:

- Added shared Python utilities under `services/common/ft_common`.
- Added skeleton entrypoints and Dockerfiles for `job-service` and all 7 workers.
- Added unit tests for config, health, object keys, and service smoke commands.
- Added `scripts/dev/smoke-services.sh`.
- Added `scripts/dev/build-images.sh`.
- Added `scripts/dev/smoke-images.sh`.
- Added `docs/IMAGE_INVENTORY.md`.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 11 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 images.
- `scripts/dev/smoke-images.sh` passes for all 8 images.
- Docker Hub push was attempted for `petoo/file-translation-job-service:0.1.0` and failed with `denied: requested access to the resource is denied`.

Commit:

- Phase 2 skeleton implementation committed as `7b5225b` with message `feat: add skeleton services`.

Next recommended step:

- Begin Phase 3 RabbitMQ command/event orchestration.

## 2026-06-10 12:35 KST - Pipeline replan started

Done:

- Stopped feature implementation work.
- Inspected current repo, branches, commits, scripts, service skeletons, and Markdown docs.
- Created branch `docs/pipeline-replan` from `bb635ab`.
- Added `docs/PIPELINE.md`.
- Added `docs/CONTRACTS.md`.
- Updated project plan and architecture for `pdf`, `docx`, and `hwpx` routes.
- Corrected the MinIO date contract from `{yy-mm-dd}` to `{YYYY-MM-DD}`.
- Preserved existing k3d/local setup records and Phase 2 skeleton work.
- Updated the object key helper and tests for the corrected date prefix.
- Aligned existing skeleton command queue defaults and smoke tests with the revised stage names.

Verified:

- Current session lightweight environment check shows Docker unavailable and `kubectl` missing from PATH.
- Custom `petoo/pdf2docx:0.5.13-py311-static` validation is documented but not runnable until Docker is restored.
- `python3 -m unittest discover -s tests` passes with 12 tests.
- `scripts/dev/smoke-services.sh` passes.

Commit:

- Pending at time of writing; see Git history for the pipeline replan commit.

Next recommended step:

- Start `feat/job-service-input-routing` from this replan commit after it is committed.
