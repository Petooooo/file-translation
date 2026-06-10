# Local Development Setup

Last updated: 2026-06-10 17:54 KST

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

## HWPX / LibreOffice H2O Validation

The HWPX route depends on two separate capabilities:

- `rhwp` parse/replace for direct HWPX text units
- LibreOffice H2O-related read/export support for final PDF/DOCX exports

Do not treat HWPX export as available until validated with local sample files or documented as a closed-network runtime dependency.
