# Validation

Last updated: 2026-06-09 22:06 KST

## Phase 0 Commands

| Command | Result |
| --- | --- |
| `pwd` | `/mnt/c/Workspace/Codex/file-translation` |
| `ls -la` | Only `.git` exists. |
| `rg --files -uu` | Only `.git` internals found. |
| `git status --short --branch` | No commits yet on `main`; `origin/main` is gone. |
| `git branch --show-current` | `main` |
| `git remote -v` | `origin` points to `git@github.com:Petooooo/file-translation.git`. |
| `git log --oneline --decorate --max-count=5` | Failed as expected because there are no commits. |
| `docker --version` | Docker `29.5.3` installed. |
| `docker info` | Docker Desktop server reachable. |
| `docker compose version` | Docker Compose `v5.1.4` installed. |
| `kubectl version --client` | Client `v1.34.1`; Kustomize `v5.7.1`. |
| `kubectl config current-context` | `docker-desktop` |
| `kubectl config get-contexts` | Only `docker-desktop` context listed. |
| `kubectl cluster-info` | Failed: connection refused to `https://kubernetes.docker.internal:6443`. |
| `helm version --short` | Failed: `helm` command not found. |
| `k3s --version` | Failed: `k3s` command not found. |
| `k3d version` | Failed: `k3d` command not found. |
| `kind version` | Failed: `kind` command not found. |
| `uname -a` | WSL2 Linux kernel `6.6.114.1-microsoft-standard-WSL2`. |

## Current Validation Summary

- Repository is empty enough for initial planning docs.
- Docker is usable.
- kubectl client exists, but no reachable Kubernetes API is available.
- Helm and local-cluster tools must be installed before Helm deployment validation.

## Known Gaps

- No services exist yet.
- No Helm chart exists yet.
- No local cluster has been created yet.
- No MinIO, RabbitMQ, or PostgreSQL instance has been deployed yet.
- Cluster smoke-test script exists, but it cannot pass until a local cluster is reachable.

## Phase 1 Commands

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/check-env.sh` | Passed. |
| `bash -n scripts/dev/bootstrap-cluster.sh` | Passed. |
| `bash -n scripts/dev/smoke-test.sh` | Passed. |
| `scripts/dev/bootstrap-cluster.sh --help` | Passed; printed usage and configurable environment variables. |
| `scripts/dev/smoke-test.sh --help` | Passed; printed usage and DNS smoke-test variables. |
| `scripts/dev/check-env.sh` | Failed as expected on this PC: Docker and kubectl passed; Helm and k3d missing; Kubernetes API not reachable. |
| `scripts/dev/bootstrap-cluster.sh` | Failed as expected: `k3d is required`. |
| `scripts/dev/smoke-test.sh` | Failed as expected: current `docker-desktop` Kubernetes API refused connection. |
| `command -v shellcheck` | Failed: `shellcheck` is not installed, so only Bash syntax validation was run. |

## Phase 1 Validation Summary

- Local dev scripts were added and syntax-checked.
- `check-env.sh` correctly reports installed and missing prerequisites.
- `bootstrap-cluster.sh` blocks before attempting cluster creation because k3d is missing.
- `smoke-test.sh` blocks because no reachable Kubernetes API exists.
- Namespace and DNS validation are still pending until Helm and k3d are installed and the local cluster is bootstrapped.

## Phase 1 Current Blocker

Install these missing tools, then rerun validation:

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh

curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
```
