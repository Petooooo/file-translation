# Troubleshooting

Last updated: 2026-06-09 20:12 KST

## kubectl cluster-info connection refused

Command:

```bash
kubectl cluster-info
```

Observed error:

```text
The connection to the server kubernetes.docker.internal:6443 was refused
```

Root cause:

- kubectl is configured for the Docker Desktop context, but the Docker Desktop Kubernetes API is not running or not reachable.

Fix:

- For this project, prefer creating a dedicated local k3d cluster in Phase 1.
- Alternative: enable Docker Desktop Kubernetes and retry, but that is less close to the expected k3s target.

Prevention:

- `scripts/dev/check-env.sh` should distinguish between kubectl installed, context configured, and API reachable.

## helm command not found

Command:

```bash
helm version --short
```

Observed error:

```text
zsh:1: command not found: helm
```

Root cause:

- Helm is not installed on this PC.

Fix:

- Install Helm as documented in `docs/LOCAL_DEV_SETUP.md`.

Prevention:

- Phase 1 environment check script should fail early with an install hint.

## k3d, k3s, and kind command not found

Commands:

```bash
k3d version
k3s --version
kind version
```

Observed error:

```text
command not found
```

Root cause:

- No local Kubernetes cluster tool is installed.

Fix:

- Install k3d first. Use kind only as fallback.

Prevention:

- Record the chosen local cluster tool and version in `docs/VALIDATION.md` after Phase 1.

