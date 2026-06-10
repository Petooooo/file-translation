# Troubleshooting

Last updated: 2026-06-10 12:35 KST

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

## scripts/dev/check-env.sh fails with missing Helm and k3d

Command:

```bash
scripts/dev/check-env.sh
```

Observed error:

```text
[FAIL] Helm client: command not found (helm)
[FAIL] k3d local cluster tool: command not found (k3d)
```

Root cause:

- The local PC has Docker and kubectl, but the selected Helm-based deployment path and k3d cluster path require Helm and k3d.

Fix:

- Install Helm and k3d using the commands in `docs/LOCAL_DEV_SETUP.md`.
- Rerun `scripts/dev/check-env.sh`.
- On PCs without passwordless sudo, install both tools into `~/.local/bin`; project scripts now prepend that path automatically.

Prevention:

- Always run `scripts/dev/check-env.sh` before trying to bootstrap or deploy.

## scripts/dev/bootstrap-cluster.sh fails because k3d is required

Command:

```bash
scripts/dev/bootstrap-cluster.sh
```

Observed error:

```text
[FAIL] k3d is required. Run scripts/dev/check-env.sh for install commands.
```

Root cause:

- `CLUSTER_PROVIDER` defaults to `k3d`, but k3d is not installed.

Fix:

- Install k3d, then rerun the bootstrap script.
- Or install kind and run `CLUSTER_PROVIDER=kind scripts/dev/bootstrap-cluster.sh` as an explicit fallback.

Prevention:

- Keep the selected provider and installed tool versions recorded in `docs/VALIDATION.md`.

## Helm install script returns non-zero after installing into ~/.local/bin

Command:

```bash
HELM_INSTALL_DIR="$HOME/.local/bin" /tmp/get_helm.sh --no-sudo
```

Observed error:

```text
helm installed into /home/peto/.local/bin/helm
helm not found. Is /home/peto/.local/bin on your $PATH?
```

Root cause:

- The Helm binary was installed, but the current zsh PATH did not include `~/.local/bin`, so the script's final validation failed.

Fix:

- Validate with `PATH="$HOME/.local/bin:$PATH" helm version --short`.
- Use the project scripts, which prepend `~/.local/bin` automatically.

Prevention:

- Keep user-local host tools in `~/.local/bin` and make project scripts include that path.

## Docker Hub push denied for petoo images

Command:

```bash
docker push petoo/file-translation-job-service:0.1.0
```

Observed error:

```text
denied: requested access to the resource is denied
```

Root cause:

- Docker could reach Docker Hub, but the current Docker credentials were not accepted for pushing to the `petoo` namespace, or the target repository/namespace permissions were not available.

Fix:

```bash
docker login -u petoo
```

Then rerun image build, smoke, and push commands.

Prevention:

- Verify Docker Hub login before release pushes.
- Record registry digests in `docs/IMAGE_INVENTORY.md` only after a successful push.

## Current session check-env cannot reach Docker or kubectl

Command:

```bash
scripts/dev/check-env.sh
```

Observed error:

```text
[FAIL] Docker server: not reachable. Start Docker Desktop or the Docker daemon.
[FAIL] kubectl client: command not found (kubectl)
```

Root cause:

- The previous k3d/k3s setup is recorded, but the current shell/session does not have a reachable Docker server and does not find `kubectl` in PATH.

Fix:

- Start Docker Desktop or the Docker daemon.
- Restore `kubectl` to PATH, or reinstall it for this environment.
- Rerun `scripts/dev/check-env.sh`.
- Reuse the existing k3d cluster if it still exists; do not recreate it blindly.

Prevention:

- Always run `scripts/dev/check-env.sh` at the start of a new PC/session and record any divergence in `docs/VALIDATION.md`.

## Custom pdf2docx image validation cannot run

Commands:

```bash
docker pull petoo/pdf2docx:0.5.13-py311-static
docker run --rm petoo/pdf2docx:0.5.13-py311-static \
  python -m pdf2docx.static_anchored.cli --help
```

Root cause:

- Docker must be reachable before validating the custom image.

Fix:

- Repair Docker access, then run the validation commands from `docs/LOCAL_DEV_SETUP.md`.

Prevention:

- Record successful image pull/help/smoke results in `docs/VALIDATION.md` before implementing `pdf2docx-worker` runtime logic.

## Job-service input routing branch had no new runtime blocker

Branch:

```text
feat/job-service-input-routing
```

Observed:

- The job-service routing implementation used in-memory repository/publisher components and did not require Docker, kubectl, RabbitMQ, PostgreSQL, or MinIO access.
- Required host-side checks passed: compileall, unittest discovery, service smoke script, and `git diff --check`.

Prevention:

- Keep later RabbitMQ/PostgreSQL integration behind the existing interfaces so local unit tests can continue to run without external services.
- Re-run `scripts/dev/check-env.sh` before any branch that needs Docker, kubectl, or the local k3d cluster.

## RabbitMQ adapter live validation pending

Branch:

```text
feat/rabbitmq-orchestration
```

Observed:

- RabbitMQ publisher/consumer adapters are covered by fake connection unit tests.
- Live broker validation was not run because the current session has no reachable Docker/kubectl/local RabbitMQ environment.
- The `job-service` Dockerfile now installs `pika==1.3.2`; image rebuild was not run for the same Docker access reason.

Fix:

- Restore Docker/kubectl access.
- Run `scripts/dev/check-env.sh`.
- Rebuild and smoke the job-service image:

```bash
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
```

- After RabbitMQ is available, run a live publish/consume smoke test with:

```bash
JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq JOB_SERVICE_EVENT_CONSUMER=rabbitmq python3 services/job-service/app.py
```

Prevention:

- Keep RabbitMQ integration tests split into brokerless unit tests and explicit live smoke tests so ordinary development does not depend on external services.

## Docker/kubectl access restored for current session

Resolved at: 2026-06-10 15:56 KST

Command:

```bash
scripts/dev/check-env.sh
```

Result:

- Docker client/server reachable.
- Docker Compose available.
- kubectl available.
- Helm and k3d available.
- Current context is `k3d-file-translation-dev`.
- Kubernetes API reachable.

Follow-up validation:

```bash
scripts/dev/smoke-test.sh
```

Result:

- Existing k3d cluster was reused.
- Nodes are Ready.
- Namespace `file-translation` exists.
- CoreDNS exists and resolves `kubernetes.default.svc.cluster.local`.

## Custom pdf2docx image validation completed

Resolved at: 2026-06-10 15:56 KST

Commands:

```bash
docker pull petoo/pdf2docx:0.5.13-py311-static
docker run --rm petoo/pdf2docx:0.5.13-py311-static \
  python -m pdf2docx.static_anchored.cli --help
docker run --rm \
  -v "$PWD/out:/work/out" \
  petoo/pdf2docx:0.5.13-py311-static \
  python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out --with-report
```

Result:

- Pull succeeded with registry digest `sha256:d3ef804baceed3516e8ce89df3a33abfde00c1fd348541c3b8ad0cb9fc404f0f`.
- Static anchored CLI help is available.
- Smoke test generated the expected PDF, DOCX, JSON report, and Markdown report.

Remaining:

- Use this fixed image/tag as the base for `feat/pdf2docx-static-worker`.

## RabbitMQ adapter image rebuild completed, live broker test still pending

Resolved:

- `scripts/dev/build-images.sh` passed after adding `pika==1.3.2`.
- `scripts/dev/smoke-images.sh` passed for all 8 service images.

Still pending:

- Live RabbitMQ publish/consume validation with an actual RabbitMQ broker.
- Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username.

Next command when credentials are available:

```bash
docker login -u petoo
```
