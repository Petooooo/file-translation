# Local Development Setup

Last updated: 2026-06-12 20:40 KST

## Current PC Inspection

Environment observed during Phase 0:

- OS/kernel: WSL2 Linux, `6.6.114.1-microsoft-standard-WSL2`
- Docker: installed, Docker Desktop server reachable, version `29.5.3`
- Docker Compose: installed, version `v5.1.4`
- kubectl: installed, client version `v1.34.1`
- kubectl current context: `docker-desktop`
- Kubernetes API: not reachable, `127.0.0.1:6443` refused connection
- Helm: not installed
- k3s: not installed
- k3d: not installed
- kind: not installed

This means local containers can run, but a usable local Kubernetes cluster and Helm are not currently available.

Phase 1 added scripts that detect this state and fail with install hints instead of pretending a cluster exists.

Phase 1 blocker resolution later installed:

- Helm `v4.2.0` in `~/.local/bin`
- k3d `v5.9.0` in `~/.local/bin`
- k3d cluster `file-translation-dev`
- Kubernetes context `k3d-file-translation-dev`
- k3s image `rancher/k3s:v1.32.13-k3s1`
- namespace `file-translation`

The project scripts prepend `~/.local/bin` to PATH when it exists, so they can find user-local Helm and k3d installs without changing shell startup files.

Current replan session note:

- Existing setup is preserved and should be revalidated before use.
- `scripts/dev/check-env.sh` currently reports Docker server not reachable and `kubectl` not found in PATH.
- Do not recreate the cluster blindly; repair/revalidate the local environment first.

Current PC continuation note from 2026-06-11 22:38 KST:

- The active distro is `Ubuntu-18.04` on WSL version 1.
- Docker Desktop's Windows-side `docker` helper is visible in PATH, but it refuses to run from WSL 1.
- `kubectl`, Helm, and k3d are not installed in PATH, and this PC's `$HOME/.local/bin` does not contain the previously recorded Helm/k3d binaries.
- `python3` is Python 3.6.9; use `python3.10` or `PYTHON_BIN=python3.10` for host validation until the default interpreter is fixed.
- Do not attempt HWPX live MinIO/RabbitMQ smoke until Docker, kubectl, Helm, and k3d are restored.

Current PC follow-up from 2026-06-11 22:52 KST:

- `/mnt/c/Windows/System32/wsl.exe -l -v` still shows only `Ubuntu-18.04` as the active project distro, running on WSL version 1.
- `docker-desktop` and `docker-desktop-data` are running on WSL version 2, so Docker Desktop itself is present.
- `/mnt/c/Windows/System32/wsl.exe --status` reports default WSL version 2, but the default distribution remains `Ubuntu-18.04`.
- `wsl --install Ubuntu-24.04 --no-launch --web-download` fails because `Ubuntu-24.04` is not a valid distro name in this WSL install list.
- `wsl --install Ubuntu --no-launch --web-download` produced no output for over two minutes, did not register a new `Ubuntu` distro, and was terminated.
- PowerShell in this environment does not find bare `wsl`; use the full path `/mnt/c/Windows/System32/wsl.exe` from this WSL session.
- Manual Windows-side setup is now required before continuing automated validation.

Required manual step:

```text
Install or enable an Ubuntu 24.04 WSL2 distro from Windows, then enable Docker Desktop WSL Integration for that distro.
```

After that, reopen the project from the Ubuntu 24.04 distro and continue with the validation commands below. Do not continue from the current Ubuntu 18.04 WSL1 distro.

Current PC follow-up from 2026-06-11 23:56 KST:

- `/mnt/c/Windows/System32/wsl.exe -l -v` now shows `Ubuntu-24.04` as the default running distro on WSL version 2.
- Codex's current shell is still attached to the older Ubuntu 18.04 WSL1 session, so validation commands were run inside Ubuntu 24.04 with:

```bash
/mnt/c/Windows/System32/wsl.exe -d Ubuntu-24.04 --cd /mnt/d/Workspaces/Codex/file-translation -- bash -lc '...'
```

- Ubuntu 24.04 reports `Ubuntu 24.04.4 LTS` and WSL2 kernel `6.18.33.1-microsoft-standard-WSL2`.
- `python3` is Python `3.12.3`, so the previous Python 3.6 blocker is resolved in Ubuntu 24.04.
- GitHub SSH authentication succeeds from Ubuntu 24.04.
- `kubectl` exists but is currently a Docker Desktop CLI-tools symlink at `/usr/local/bin/kubectl` and returned `Input/output error` while Docker Desktop integration was unhealthy.
- Helm `v3.21.0` was installed into `/home/peto/.local/bin/helm`.
- k3d `v5.9.0` was installed into `/home/peto/.local/bin/k3d`.
- Docker Desktop was started from Windows, and `docker version` / `docker ps` succeeded once, but later the Docker Desktop Linux CLI symlink segfaulted and the Docker socket stopped responding.
- `curl --unix-socket /var/run/docker.sock http://localhost/_ping` fails, and `docker-desktop` is not running in `wsl -l -v`.
- Do not continue project validation or HWPX live smoke until Docker Desktop WSL integration is stable and `docker ps` repeatedly succeeds inside Ubuntu 24.04.

Required manual step:

```text
Open Docker Desktop on Windows and verify the engine is running.
Then check Settings -> Resources -> WSL Integration and ensure Ubuntu-24.04 is enabled.
Apply & Restart if needed, then rerun docker version and docker ps from Ubuntu-24.04.
```

Current PC resolved state from 2026-06-12:

- Codex is now running this repo from `Ubuntu-24.04` on WSL2 at `/mnt/d/Workspaces/Codex/file-translation`.
- `cat /etc/os-release` reports `Ubuntu 24.04.4 LTS`.
- `uname -a` reports WSL2 kernel `6.18.33.1-microsoft-standard-WSL2`.
- `python3` is Python `3.12.3`.
- GitHub SSH authentication succeeds as `Petooooo`.
- Docker Desktop WSL integration is stable: `docker version`, `docker ps`, and Docker socket `_ping` pass.
- `kubectl` client is `v1.28.2`.
- Helm `v3.21.0` and k3d `v5.9.0` are installed in `/home/peto/.local/bin`.
- Local k3d cluster `file-translation-dev` exists with context `k3d-file-translation-dev`.
- Namespace `file-translation` is Active, both k3d nodes are Ready, and CoreDNS is available.

Repeatable current-PC validation sequence:

```bash
docker version
docker ps
kubectl version --client
helm version
k3d version
python3 -m compileall -q services tests
python3 -m unittest discover -s tests
PYTHON_BIN=python3 scripts/dev/smoke-services.sh
PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh
PYTHON_BIN=python3 scripts/dev/smoke-long-running-stage-safety.sh
PYTHON_BIN=python3 scripts/dev/smoke-stale-lease-reconciler.sh
PYTHON_BIN=python3 scripts/dev/smoke-retry-backoff-dlq.sh
PYTHON_BIN=python3 scripts/dev/smoke-monitoring-readiness.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
scripts/dev/smoke-pdf2hwpx-live.sh
scripts/dev/smoke-hwpx-live.sh
```

Recommended repair order on this PC:

```powershell
wsl --shutdown
wsl --set-version Ubuntu-18.04 2
wsl -l -v
```

Then enable Docker Desktop WSL integration for `Ubuntu-18.04`, reopen WSL, and reinstall or restore Helm, k3d, and kubectl before running:

```bash
scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
python3.10 -m compileall -q services tests
python3.10 -m unittest discover -s tests
PYTHON_BIN=python3.10 scripts/dev/smoke-services.sh
PYTHON_BIN=python3.10 scripts/dev/smoke-hwpx-local.sh
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
```

## Recommended Local Cluster Path

Use `k3d` by default because it runs k3s in Docker and is closer to the expected closed-network k3s target than kind. Docker and kubectl are already available on this PC, satisfying the core k3d prerequisites.

Fallback: use `kind` if k3d installation or cluster startup fails. kind is also Docker-based and widely reproducible, but it is less close to k3s.

Official references checked during planning:

- k3d overview and install: https://k3d.io/stable/
- Helm install: https://helm.sh/docs/v3/intro/install/
- kind quick start: https://kind.sigs.k8s.io/docs/user/quick-start/

## Install Missing Tools

Install Helm using the official script flow:

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh
helm version --short
```

Install k3d using the official install script:

```bash
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
k3d version
```

Optional fallback install for kind on Linux AMD64:

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.32.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
kind version
```

## Script Usage

Run the environment check first:

```bash
scripts/dev/check-env.sh
```

Create or reuse the local cluster:

```bash
scripts/dev/bootstrap-cluster.sh
```

Validate namespace and cluster DNS:

```bash
scripts/dev/smoke-test.sh
```

Defaults:

```text
CLUSTER_PROVIDER=k3d
CLUSTER_NAME=file-translation-dev
NAMESPACE=file-translation
K3D_API_PORT=127.0.0.1:6550
K3D_HTTP_PORT=8080
K3D_IMAGE=rancher/k3s:v1.32.13-k3s1
```

Use kind fallback only when intentionally needed:

```bash
CLUSTER_PROVIDER=kind scripts/dev/bootstrap-cluster.sh
```

The scripts do not install host tools automatically. Install missing tools manually using the commands above, then rerun the scripts.

## Helm Local Stack

After building local images, deploy the full MSA stack into the local k3d/k3s namespace:

```bash
scripts/dev/build-images.sh
scripts/dev/helm-install-local.sh
scripts/dev/smoke-helm-local.sh
```

`scripts/dev/helm-install-local.sh` performs:

- `helm lint charts/file-translation`
- `helm template file-translation charts/file-translation -f charts/file-translation/values.local.yaml`
- local project image import into k3d cluster `file-translation-dev`
- `helm upgrade --install file-translation charts/file-translation -f charts/file-translation/values.local.yaml`
- queue init Job wait
- MinIO bucket init Job wait
- rollout wait for `job-service`, workers, PostgreSQL, RabbitMQ, and MinIO

`scripts/dev/smoke-helm-local.sh` verifies:

- queue init Job completed
- MinIO bucket init Job completed
- all Deployments are rolled out
- `job-service /healthz`
- `job-service /readyz`
- `job-service /admin/health`
- `/admin` lightweight UI loads
- one in-cluster HWPX route E2E job reaches `completed`

Local Helm access:

```bash
kubectl -n file-translation port-forward svc/file-translation-job-service 8080:8080
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/readyz
curl -fsS http://127.0.0.1:8080/admin/health
```

Physical RabbitMQ DLX/DLQ is disabled in `values.local.yaml` because current app code declares queues without matching DLX arguments. Logical DLQ remains enabled in job-service/PostgreSQL state.

## k3d Cluster Bootstrap

The initial cluster should be disposable and local-only.

```bash
k3d cluster create file-translation-dev \
  --agents 1 \
  --image rancher/k3s:v1.32.13-k3s1 \
  --api-port 127.0.0.1:6550 \
  --port "8080:80@loadbalancer"

kubectl config use-context k3d-file-translation-dev
kubectl get nodes
kubectl create namespace file-translation
kubectl get namespace file-translation
```

Phase 1 converted this into scripts:

```text
scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
```

## Planned Helm Deployment Shape

The final deployment target is:

```text
charts/file-translation/
```

Expected values files:

```text
charts/file-translation/values.yaml
charts/file-translation/values.local.yaml
charts/file-translation/values.closed.example.yaml
```

The chart should support:

- local bundled MinIO, RabbitMQ, and PostgreSQL
- external MinIO, RabbitMQ, and PostgreSQL for closed-network deployments
- external closed-network translation API endpoint
- `pdf`, `docx`, and `hwpx` route configuration
- custom `pdf2docx` image override, defaulting to `petoo/pdf2docx:0.5.13-py311-static`
- HWPX/rhwp and LibreOffice H2O validation flags
- ConfigMap templates for non-secret settings
- Secret templates or existing secret references for credentials
- configurable image repositories and explicit tags
- service and deployment templates for all project services

## Validation Commands

Run these after installing missing tools:

```bash
docker info
helm version --short
k3d version
kubectl cluster-info
kubectl get nodes -o wide
kubectl create namespace file-translation --dry-run=client -o yaml
```

Record all validation results in `docs/VALIDATION.md`.

## Custom pdf2docx Image Validation

Validate the static anchored converter image when Docker is available:

```bash
docker pull petoo/pdf2docx:0.5.13-py311-static
```

```bash
docker run --rm petoo/pdf2docx:0.5.13-py311-static \
  python -m pdf2docx.static_anchored.cli --help
```

Smoke test:

```bash
mkdir -p out

docker run --rm \
  -v "$PWD/out:/work/out" \
  petoo/pdf2docx:0.5.13-py311-static \
  python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out --with-report
```

Expected files:

```text
out/sample.pdf
out/sample.static.docx
out/sample.static.report.json
out/sample.static.report.md
```

Record pull/help/smoke results in `docs/VALIDATION.md`.

## pdf2docx-worker Local Container Validation

After `pdf2docx-worker` is built from the static anchored base image, validate the worker wrapper itself:

```bash
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
```

Create a sample PDF with the validated base image, then run the worker conversion wrapper:

```bash
rm -rf out/pdf2docx-worker
mkdir -p out/pdf2docx-worker

docker run --rm \
  -v "$PWD/out/pdf2docx-worker:/work/out" \
  petoo/pdf2docx:0.5.13-py311-static \
  python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out --with-report

docker run --rm \
  -v "$PWD/out/pdf2docx-worker:/work/out" \
  petoo/file-translation-pdf2docx-worker:0.1.0 \
  python /app/service/worker.py \
    --convert-local \
    --input /work/out/sample.pdf \
    --output /work/out/worker.static.docx \
    --with-report \
    --overwrite
```

Expected worker outputs:

```text
out/pdf2docx-worker/worker.static.docx
out/pdf2docx-worker/worker.static.report.json
out/pdf2docx-worker/worker.static.report.md
```

## pdf2docx-worker Live MinIO/RabbitMQ Smoke

After `feat/pdf2docx-worker-artifacts`, run a live Docker smoke for the worker command/event path:

```bash
scripts/dev/smoke-pdf2docx-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-pdf2docx-worker:0.1.0
```

It then:

- generates a sample PDF with `petoo/pdf2docx:0.5.13-py311-static`
- uploads it to `file-translation/2026-01-21/12345678/a8f3k2p9/input/original.pdf`
- publishes a command to `q.commands.pdf2docx`
- waits for `q.events.stage_completed`
- verifies the converted DOCX and optional report artifacts exist in MinIO

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/customfile \
JOB_ID=custom-pdf2docx-smoke \
scripts/dev/smoke-pdf2docx-live.sh
```

Keep containers for debugging:

```bash
KEEP_LIVE_SMOKE=1 scripts/dev/smoke-pdf2docx-live.sh
```

The RabbitMQ/MinIO-backed worker mode is:

```bash
PDF2DOCX_ENABLE_REPORTS=true \
MINIO_ACCESS_KEY=minioadmin \
MINIO_SECRET_KEY=minioadmin \
RABBITMQ_USERNAME=guest \
RABBITMQ_PASSWORD=guest \
python3 services/pdf2docx-worker/worker.py --consume
```

Only run this after RabbitMQ and MinIO are available locally or through Kubernetes service DNS. The worker publishes `stage.completed` or `stage.failed` events only; it does not enqueue the next stage.

## docx-extract-worker Local Container Validation

After `docx-extract-worker` is built, validate local extraction with a sample DOCX:

```bash
python3 services/docx-extract-worker/worker.py \
  --extract-local \
  --input out/docx-extract-worker/sample.docx \
  --output out/docx-extract-worker/text_units.json \
  --job-id local-docx \
  --input-type docx \
  --source-lang en \
  --target-lang ko
```

Container validation:

```bash
docker run --rm \
  -v "$PWD/out/docx-extract-worker:/work/out" \
  petoo/file-translation-docx-extract-worker:0.1.0 \
  python /app/service/worker.py \
    --extract-local \
    --input /work/out/sample.docx \
    --output /work/out/container.text_units.json \
    --job-id container-docx \
    --input-type docx \
    --source-lang en \
    --target-lang ko
```

Expected output:

```text
out/docx-extract-worker/text_units.json
out/docx-extract-worker/container.text_units.json
```

## docx-extract-worker Live MinIO/RabbitMQ Smoke

After `feat/pdf-docx-pipeline`, run a live Docker smoke for the `docx_extract` command/event path:

```bash
scripts/dev/smoke-docx-extract-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-docx-extract-worker:0.1.0
```

It then:

- creates a minimal sample DOCX
- uploads it to `file-translation/2026-01-21/12345678/docxsmoke1/input/original.docx`
- publishes a command to `q.commands.docx_extract`
- waits for `q.events.stage_completed`
- verifies `02_extract/text_units.json` exists in MinIO and contains two text units

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/customdocx \
JOB_ID=custom-docx-extract-smoke \
scripts/dev/smoke-docx-extract-live.sh
```

## translate-worker Local Container Validation

After `translate-worker` is built, validate local mock translation with a sample `text_units.json`:

```bash
python3 services/translate-worker/worker.py \
  --translate-local \
  --input out/docx-translate-worker/text_units.json \
  --output out/docx-translate-worker/translated_units.json \
  --target-lang ko
```

Container validation:

```bash
docker run --rm \
  -v "$PWD/out/docx-translate-worker:/work/out" \
  petoo/file-translation-translate-worker:0.1.0 \
  python /app/service/worker.py \
    --translate-local \
    --input /work/out/text_units.json \
    --output /work/out/container.translated_units.json \
    --target-lang ko
```

Expected output:

```text
out/docx-translate-worker/translated_units.json
out/docx-translate-worker/container.translated_units.json
```

## translate-worker Live MinIO/RabbitMQ Smoke

After `feat/pdf-docx-pipeline` includes `docx_translate`, run a live Docker smoke for the `docx_translate` command/event path:

```bash
scripts/dev/smoke-docx-translate-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-translate-worker:0.1.0
```

It then:

- creates a sample `text_units.json`
- uploads it to `file-translation/2026-01-21/12345678/translatesmoke1/02_extract/text_units.json`
- starts `translate-worker --consume` with `TRANSLATION_PROVIDER=mock`
- publishes a command to `q.commands.docx_translate`
- waits for at least one `q.events.progress` event and one `q.events.stage_completed` event
- verifies `03_translate/translated_units.json` exists in MinIO and contains mock translations

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/customtranslate \
JOB_ID=custom-docx-translate-smoke \
scripts/dev/smoke-docx-translate-live.sh
```

## docx-replace-worker Local Container Validation

After `docx-replace-worker` is built, validate replacement with a sample DOCX, `text_units.json`, and `translated_units.json`:

```bash
python3 services/docx-replace-worker/worker.py \
  --replace-local \
  --input-docx out/docx-replace-worker/input.docx \
  --text-units out/docx-replace-worker/text_units.json \
  --translated-units out/docx-replace-worker/translated_units.json \
  --output out/docx-replace-worker/translated.docx
```

Container validation:

```bash
docker run --rm \
  -v "$PWD/out/docx-replace-worker:/work/out" \
  petoo/file-translation-docx-replace-worker:0.1.0 \
  python /app/service/worker.py \
    --replace-local \
    --input-docx /work/out/input.docx \
    --text-units /work/out/text_units.json \
    --translated-units /work/out/translated_units.json \
    --output /work/out/container.translated.docx
```

Expected output:

```text
out/docx-replace-worker/translated.docx
out/docx-replace-worker/container.translated.docx
```

The current MVP replaces only `word/document.xml` text runs described by `text_units.json`.

## docx-replace-worker Live MinIO/RabbitMQ Smoke

After `feat/pdf-docx-pipeline` includes `docx_replace`, run a live Docker smoke for the `docx_replace` command/event path:

```bash
scripts/dev/smoke-docx-replace-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-docx-replace-worker:0.1.0
```

It then:

- creates a minimal sample DOCX
- creates matching `text_units.json` and `translated_units.json`
- uploads all inputs under `file-translation/2026-01-21/12345678/replacesmoke1`
- publishes a command to `q.commands.docx_replace`
- waits for `q.events.stage_completed`
- verifies `04_replace/translated.docx` exists in MinIO and contains the mock translated text

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/customreplace \
JOB_ID=custom-docx-replace-smoke \
scripts/dev/smoke-docx-replace-live.sh
```

## libreoffice-worker docx_export Local Container Validation

After `libreoffice-worker` is built, validate DOCX export with a translated DOCX:

```bash
python3 services/libreoffice-worker/worker.py \
  --export-local \
  --input out/docx-export-worker/translated.docx \
  --final-docx out/docx-export-worker/final.docx \
  --final-pdf out/docx-export-worker/final.pdf
```

Container validation:

```bash
docker run --rm \
  -v "$PWD/out/docx-export-worker:/work/out" \
  petoo/file-translation-libreoffice-worker:0.1.0 \
  python /app/service/worker.py \
    --export-local \
    --input /work/out/translated.docx \
    --final-docx /work/out/container.final.docx \
    --final-pdf /work/out/container.final.pdf
```

Expected output:

```text
out/docx-export-worker/final.docx
out/docx-export-worker/final.pdf
out/docx-export-worker/container.final.docx
out/docx-export-worker/container.final.pdf
```

The local default is `DOCX_EXPORT_PDF_MODE=placeholder`. Real PDF export requires a runtime image with LibreOffice and `DOCX_EXPORT_PDF_MODE=libreoffice`.

## libreoffice-worker docx_export Live MinIO/RabbitMQ Smoke

After `feat/pdf-docx-pipeline` includes `docx_export`, run a live Docker smoke for the `docx_export` command/event path:

```bash
scripts/dev/smoke-docx-export-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-libreoffice-worker:0.1.0
```

It then:

- creates a minimal translated DOCX
- uploads it to `file-translation/2026-01-21/12345678/exportsmoke1/04_replace/translated.docx`
- publishes a command to `q.commands.docx_export`
- waits for `q.events.stage_completed`
- verifies `05_export/final.docx` and `05_export/final.pdf` exist in MinIO
- verifies the final DOCX text and placeholder PDF header

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/customexport \
JOB_ID=custom-docx-export-smoke \
scripts/dev/smoke-docx-export-live.sh
```

## libreoffice-worker docx_marker Local Container Validation

After `libreoffice-worker` is built, validate marker DOCX generation with a final DOCX:

```bash
python3 services/libreoffice-worker/worker.py \
  --mark-local \
  --input out/docx-marker-worker/final.docx \
  --marker-docx out/docx-marker-worker/marker.docx
```

Container validation:

```bash
docker run --rm \
  -v "$PWD/out/docx-marker-worker:/work/out" \
  petoo/file-translation-libreoffice-worker:0.1.0 \
  python /app/service/worker.py \
    --mark-local \
    --input /work/out/final.docx \
    --marker-docx /work/out/container.marker.docx
```

Expected output:

```text
out/docx-marker-worker/marker.docx
out/docx-marker-worker/container.marker.docx
```

The local default marker token is `DOCX_MARKER_TOKEN=¡`.

## libreoffice-worker docx_marker Live MinIO/RabbitMQ Smoke

After `feat/pdf-docx-pipeline` includes `docx_marker`, run a live Docker smoke for the `docx_marker` command/event path:

```bash
scripts/dev/smoke-docx-marker-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-libreoffice-worker:0.1.0
```

It then:

- creates a minimal final DOCX
- uploads it to `file-translation/2026-01-21/12345678/markersmoke1/05_export/final.docx`
- publishes a command to `q.commands.docx_marker`
- waits for `q.events.stage_completed`
- verifies `05_export/marker.docx` exists in MinIO
- verifies spaces in DOCX text nodes were replaced with `¡`

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/custommarker \
JOB_ID=custom-docx-marker-smoke \
scripts/dev/smoke-docx-marker-live.sh
```

## pdf2hwpx-worker Local Container Validation

After `pdf2hwpx-worker` is built, validate placeholder HWPX generation with a marker DOCX:

```bash
python3 services/pdf2hwpx-worker/worker.py \
  --generate-local \
  --input out/pdf2hwpx-worker/marker.docx \
  --output out/pdf2hwpx-worker/final.hwpx \
  --job-id local-pdf2hwpx \
  --input-type docx \
  --object-prefix 2026-01-21/12345678/localpdf2hwpx
```

Container validation:

```bash
docker run --rm \
  -v "$PWD/out/pdf2hwpx-worker:/work/out" \
  petoo/file-translation-pdf2hwpx-worker:0.1.0 \
  python /app/service/worker.py \
    --generate-local \
    --input /work/out/marker.docx \
    --output /work/out/container.final.hwpx \
    --job-id container-pdf2hwpx \
    --input-type docx \
    --object-prefix 2026-01-21/12345678/containerpdf2hwpx
```

Expected output:

```text
out/pdf2hwpx-worker/final.hwpx
out/pdf2hwpx-worker/container.final.hwpx
```

The current output is a placeholder HWPX zip containing `placeholder.json` and `source/marker.docx`.

## pdf2hwpx-worker Live MinIO/RabbitMQ Smoke

After `feat/pdf-docx-pipeline` includes `pdf2hwpx`, run a live Docker smoke for the `pdf2hwpx` command/event path:

```bash
scripts/dev/smoke-pdf2hwpx-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-pdf2hwpx-worker:0.1.0
```

It then:

- creates a minimal marker DOCX
- uploads it to `file-translation/2026-01-21/12345678/hwpxsmoke1/05_export/marker.docx`
- publishes a command to `q.commands.pdf2hwpx`
- waits for `q.events.stage_completed`
- verifies `06_hwpx/final.hwpx` exists in MinIO
- verifies the placeholder HWPX zip metadata and embedded marker DOCX

Useful overrides:

```bash
OBJECT_PREFIX=2026-06-10/12345678/customhwpx \
JOB_ID=custom-pdf2hwpx-smoke \
scripts/dev/smoke-pdf2hwpx-live.sh
```

## HWPX / LibreOffice H2O Validation

The HWPX route depends on two separate capabilities:

- `rhwp` parse/replace for direct HWPX text units
- LibreOffice H2O-related read/export support for final PDF/DOCX exports

Do not treat HWPX export as available until validated with local sample files or documented as a closed-network runtime dependency.

Current local skeleton smoke:

```bash
scripts/dev/smoke-hwpx-local.sh
```

The script runs without MinIO/RabbitMQ and verifies:

- sample `.hwpx` creation through the local zip/XML stub
- `hwpx_extract` local text unit extraction
- `hwpx_translate` local mock translation through `translate-worker`
- `hwpx_replace` local HWPX replacement
- `hwpx_export` local placeholder final HWPX/DOCX/PDF artifact creation

This does not validate real `rhwp` or LibreOffice H2O. Keep the local flags disabled until those dependencies are actually available:

```text
HWPX_RHWP_ENABLED=false
HWPX_H2O_EXPORT_ENABLED=false
```

## HWPX Live MinIO/RabbitMQ Smoke

After Docker, k3d, image, and local HWPX validation pass, run:

```bash
scripts/dev/smoke-hwpx-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
petoo/file-translation-hwpx-worker:0.1.0
petoo/file-translation-translate-worker:0.1.0
```

It then:

- creates a placeholder `.hwpx` through the current zip/XML stub
- uploads it to `file-translation/2026-01-21/12345678/hwpxlivesmoke1/input/original.hwpx`
- publishes `hwpx_extract` to `q.commands.hwpx_extract`
- verifies `hwpx-worker --consume-extract` writes `02_extract/text_units.json`
- verifies `stage.completed` for `hwpx_extract`
- publishes `hwpx_translate` to `q.commands.hwpx_translate`
- verifies `translate-worker --consume-hwpx` writes `03_translate/translated_units.json`
- verifies at least one `translate.progress` event and `stage.completed` for `hwpx_translate`

This smoke validates the live command/event/artifact contract for the extract-to-translate HWPX route. It does not validate real `rhwp`, real LibreOffice H2O export, `hwpx_replace`, `hwpx_export`, or full job-service orchestration.

## job-service Orchestration Live Smoke

After image rebuild/smoke and the HWPX live smoke pass, run:

```bash
scripts/dev/smoke-job-orchestration-live.sh
```

The script starts disposable local containers for:

```text
minio/minio:RELEASE.2025-02-07T23-21-09Z
rabbitmq:3.13-management
postgres:16-alpine
petoo/file-translation-job-service:0.1.0
petoo/file-translation-hwpx-worker:0.1.0
```

`job-service` runs with:

```text
JOB_SERVICE_REPOSITORY=postgres
JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq
JOB_SERVICE_EVENT_CONSUMER=rabbitmq
```

The smoke verifies:

- PostgreSQL is reachable and `job-service` creates/updates the `jobs` JSONB table
- RabbitMQ event queues are declared and consumed by `job-service`
- `pdf2docx stage.completed` publishes `q.commands.docx_extract`
- `docx_extract stage.completed` publishes `q.commands.docx_translate`
- `hwpx_extract stage.completed` publishes `q.commands.hwpx_translate`
- a `cancel_requested` DOCX job moves to `cancelled` and does not publish the next command

This is not a Helm/local-stack deployment. It is a Docker disposable live smoke for the orchestration contract.

## HWPX Replace/Export Live Smoke

After `scripts/dev/smoke-job-orchestration-live.sh` passes, run:

```bash
scripts/dev/smoke-hwpx-replace-export-live.sh
```

The smoke validates the placeholder HWPX route through real disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `hwpx-worker`, `translate-worker`, and `libreoffice-worker`:

```text
hwpx_extract
-> hwpx_translate
-> hwpx_replace
-> hwpx_export
-> email_send
```

It stops at `current_stage=email_send`; email delivery/end-state is covered by the next smoke.

## email_send End-State Live Smoke

After `scripts/dev/smoke-hwpx-replace-export-live.sh` passes, run:

```bash
scripts/dev/smoke-email-end-state-live.sh
```

The smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, and `email-worker`. It uses synthetic upstream HWPX completion events to focus on the terminal email contract:

- `job-service` reaches `current_stage=email_send`
- `job-service` publishes `q.commands.email_send`
- `email-worker` calls `job-service` sendability before mock provider execution
- `email-worker` writes `reports/email_report.json` to MinIO
- `email-worker` publishes `email_send stage.completed`
- `job-service` consumes the event and persists `status=completed`, `current_stage=completed`

This is still a disposable Docker live smoke. It does not deploy Helm resources and it does not call a real email provider.

## HWPX Route-Level E2E Smoke

After the stage-level live smokes pass, run:

```bash
scripts/dev/smoke-hwpx-route-e2e.sh
```

This is the first route-level E2E smoke. It starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `hwpx-worker`, `translate-worker`, `libreoffice-worker`, and `email-worker`, then validates:

```text
job-service create HWPX job
-> hwpx_extract
-> hwpx_translate
-> hwpx_replace
-> hwpx_export
-> email_send
-> completed
```

The smoke verifies final placeholder artifacts, `reports/email_report.json`, PostgreSQL JSONB terminal state, empty RabbitMQ command queues, and cancellation gates before the successful route run.

This is not a Helm/local-stack deployment. Keep Helm work deferred until HWPX, DOCX, and PDF route-level E2E smoke coverage is stable.

## DOCX Route-Level E2E Smoke

After the HWPX route-level smoke passes, run:

```bash
scripts/dev/smoke-docx-route-e2e.sh
```

The smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `docx-extract-worker`, `translate-worker`, `docx-replace-worker`, `libreoffice-worker`, `pdf2hwpx-worker`, and `email-worker`, then validates:

```text
job-service create DOCX job
-> docx_extract
-> docx_translate
-> docx_replace
-> docx_export
-> docx_marker
-> pdf2hwpx
-> email_send
-> completed
```

The smoke verifies final DOCX/PDF artifacts, marker DOCX, placeholder HWPX, `reports/email_report.json`, PostgreSQL JSONB terminal state, empty RabbitMQ command queues, and cancellation gates before the successful route run.

This is not a Helm/local-stack deployment. Keep Helm work deferred until PDF route-level E2E smoke coverage is stable.

## PDF Route-Level E2E Smoke

After the DOCX route-level smoke passes, run:

```bash
scripts/dev/smoke-pdf-route-e2e.sh
```

The smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `pdf2docx-worker`, `docx-extract-worker`, `translate-worker`, `docx-replace-worker`, `libreoffice-worker`, `pdf2hwpx-worker`, and `email-worker`, then validates:

```text
job-service create PDF job
-> pdf2docx
-> docx_extract
-> docx_translate
-> docx_replace
-> docx_export
-> docx_marker
-> pdf2hwpx
-> email_send
-> completed
```

The smoke generates its sample PDF with `petoo/pdf2docx:0.5.13-py311-static`, runs `pdf2docx-worker` with `PDF2DOCX_ENABLE_REPORTS=true`, and verifies `01_pdf2docx/converted.docx`, `reports/pdf2docx.report.json`, and `reports/pdf2docx.report.md` before the downstream DOCX-route checks.

It also verifies final DOCX/PDF artifacts, marker DOCX, placeholder HWPX, `reports/email_report.json`, PostgreSQL JSONB terminal state, empty RabbitMQ command queues, and cancellation gates before the successful route run.

This is not a Helm/local-stack deployment. With HWPX, DOCX, and PDF route-level E2E coverage in place, run the reliability smokes before Helm/local-stack work.

## Long-Running Reliability Smokes

Run:

```bash
PYTHON_BIN=python3 scripts/dev/smoke-long-running-stage-safety.sh
PYTHON_BIN=python3 scripts/dev/smoke-stale-lease-reconciler.sh
PYTHON_BIN=python3 scripts/dev/smoke-retry-backoff-dlq.sh
```

These smokes validate job-service-created command claim/ack behavior, heartbeat metadata, duplicate command/event no-op behavior, stale lease retry/fail/cancel recovery, delayed retry/backoff, logical DLQ metadata, and stale `email_send` no-auto-retry behavior. They do not create large 2,000-page input files and do not deploy Helm resources.
