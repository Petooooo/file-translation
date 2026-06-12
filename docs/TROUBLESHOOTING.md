# Troubleshooting

Last updated: 2026-06-12 08:00 KST

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

## pdf2docx-worker static runtime has no local blocker

Branch:

```text
feat/pdf2docx-static-worker
```

Observed:

- `pdf2docx-worker` builds from `petoo/pdf2docx:0.5.13-py311-static`.
- Container smoke passes.
- `worker.py --convert-local` successfully converts a sample PDF and writes JSON/Markdown reports.
- Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username.

Remaining:

- Implement RabbitMQ command consumption and MinIO artifact transfer for real pipeline operation.
- Run `docker login -u petoo` before pushing refreshed `petoo/file-translation-*` images.

## pdf2docx-worker live MinIO/RabbitMQ smoke completed

Branch:

```text
feat/pdf2docx-worker-artifacts
```

Observed before live smoke:

- Brokerless unit tests cover MinIO helper behavior, RabbitMQ JSON ack/nack behavior, artifact key calculation, and event payloads.
- `pdf2docx-worker --consume` was implemented but had not yet been exercised against live MinIO/RabbitMQ services.
- Docker Hub push was not attempted because `docker info` did not report a logged-in Docker Hub username.

Resolved at: 2026-06-10 17:23 KST

- `scripts/dev/smoke-pdf2docx-live.sh` now starts disposable MinIO/RabbitMQ containers.
- The smoke creates bucket `file-translation`.
- The smoke uploads a sample PDF to `2026-01-21/12345678/a8f3k2p9/input/original.pdf`.
- The smoke publishes a `pdf2docx` command to `q.commands.pdf2docx`.
- The smoke verifies `q.events.stage_completed` contains output keys and MinIO contains converted DOCX/report artifacts.

Remaining:

- Docker Hub push still requires `docker login -u petoo`.
- Helm/local-stack validation still needs a Kubernetes-native MinIO/RabbitMQ deployment path.

## pdf2docx live smoke hangs while waiting for MinIO/RabbitMQ

Command:

```bash
scripts/dev/smoke-pdf2docx-live.sh
```

Observed behavior:

- The script started MinIO and RabbitMQ successfully.
- It then hung at `Waiting for MinIO/RabbitMQ and seeding input object`.
- `docker ps` showed only the MinIO/RabbitMQ containers plus the seed driver container.

Root cause:

- The smoke script used service names `minio` and `rabbitmq` from inside other containers, but the Docker network only had container names like `ft-minio-live` and `ft-rabbitmq-live`.
- Docker did not have explicit network aliases for `minio` and `rabbitmq`, so the seed/publish containers could not resolve the same names used by Kubernetes-style service DNS.

Fix:

- Add `--network-alias minio` to the MinIO container.
- Add `--network-alias rabbitmq` to the RabbitMQ container.
- Give the seed and publish driver containers stable names so cleanup can remove them if the smoke is interrupted.

Prevention:

- Keep Docker smoke service names aligned with Kubernetes service DNS names whenever possible.
- If a Docker live smoke hangs, check network endpoints with:

```bash
docker ps -a --filter network=ft-pdf2docx-live
docker logs ft-minio-live
docker logs ft-rabbitmq-live
```

Resolved:

- `scripts/dev/smoke-pdf2docx-live.sh` passed after adding the aliases and stable driver container names.

## docx-extract-worker branch had no new runtime blocker

Branch:

```text
feat/pdf-docx-pipeline
```

Observed:

- Host unit tests, service smoke, image build, image smoke, local extraction, container extraction, and live MinIO/RabbitMQ smoke all passed.
- The live smoke uses the same explicit Docker network alias pattern as `smoke-pdf2docx-live.sh`.

Known limitations:

- The MVP extracts from `word/document.xml` only.
- Headers, footers, comments, tracked changes, and richer DOCX replacement edge cases are not yet covered.
- This is acceptable for the first `text_units.json` producer, but replacement work must revisit location fidelity.

Prevention:

- Keep extraction and replacement tests paired when `docx_replace` is implemented.
- Add sample DOCX fixtures that include headers/footers before claiming full DOCX coverage.

## docx_translate branch had no new runtime blocker

Branch:

```text
feat/pdf-docx-pipeline
```

Observed:

- Host unit tests, service smoke, image build, image smoke, local translation, container translation, and live MinIO/RabbitMQ smoke all passed.
- Local translation uses `TRANSLATION_PROVIDER=mock` by default and does not require paid keys or external network services.
- The live smoke uses the same explicit Docker network alias pattern as the previous worker live smoke scripts.

Known limitations:

- The mock provider is intentionally deterministic and does not perform real translation.
- The HTTP provider is a skeleton for the internal API shape and has not been validated against the real closed-network translation service.
- HWPX `hwpx_translate` remains separate work.

Prevention:

- Keep provider-specific tests isolated from artifact/event tests.
- Validate the real internal translation API with sample `string` + `uid` requests before enabling it outside mock mode.

## docx_replace branch had no new runtime blocker

Branch:

```text
feat/pdf-docx-pipeline
```

Observed:

- Host unit tests, service smoke, image build, image smoke, local replacement, container replacement, and live MinIO/RabbitMQ smoke all passed.
- Local replacement uses `text_units.json` locations and `translated_units.json` translations by `uid`.
- The live smoke uses explicit Docker network aliases for MinIO and RabbitMQ and removes disposable containers/network during cleanup.

Known limitations:

- The current MVP replaces `word/document.xml` only.
- Headers, footers, comments, text boxes, tracked changes, split text across complex runs, and other DOCX parts are not yet covered.
- XML namespace serialization may normalize the main document part when writing the replaced DOCX.

Prevention:

- Add paired extraction/replacement fixtures before expanding DOCX coverage.
- Do not claim complete DOCX replacement until headers, footers, and richer run segmentation are validated.

## docx_export branch had no new runtime blocker

Branch:

```text
feat/pdf-docx-pipeline
```

Observed:

- Host unit tests, service smoke, image build, image smoke, local export, container export, and live MinIO/RabbitMQ smoke all passed.
- The live smoke uses `DOCX_EXPORT_PDF_MODE=placeholder` and verifies final DOCX plus placeholder PDF artifacts.
- The disposable Docker containers and network were removed after the smoke.

Known limitations:

- The current PDF is a placeholder, not a real LibreOffice conversion.
- The runtime image does not install LibreOffice yet.
- `DOCX_EXPORT_PDF_MODE=libreoffice` is present as a code path but has not been validated in this project runtime.

Prevention:

- Do not mark real PDF export complete until a LibreOffice-containing image is built and validated with sample DOCX files.
- Keep placeholder mode explicit in local Helm values and smoke tests until real conversion is proven.

## docx_marker branch had no new runtime blocker

Branch:

```text
feat/pdf-docx-pipeline
```

Observed:

- Host unit tests, service smoke, image build, image smoke, local marker generation, container marker generation, and live MinIO/RabbitMQ smoke all passed.
- The marker worker runs from the `libreoffice-worker` image using `--consume-marker`.
- The live smoke removed disposable Docker containers and network during cleanup.

Known limitations:

- The marker MVP replaces spaces only in `word/*.xml` `w:t` text nodes.
- XML namespace serialization may normalize modified DOCX XML parts.
- The marker output is an intermediate artifact for the later `pdf2hwpx` placeholder/real library stage, not a user-facing final DOCX.

Prevention:

- Keep marker generation separate from `docx_export` so `05_export/final.docx` remains unmodified.
- Add richer DOCX samples before claiming marker coverage for headers, footers, text boxes, or other complex document parts.

## pdf2hwpx branch had no new runtime blocker

Branch:

```text
feat/pdf-docx-pipeline
```

Observed:

- Host unit tests, service smoke, image build, image smoke, local placeholder generation, container placeholder generation, and live MinIO/RabbitMQ smoke all passed.
- The live smoke removed disposable Docker containers and network during cleanup.

Known limitations:

- The generated `.hwpx` is a placeholder zip package, not a real HWPX conversion.
- The real custom `pdf2hwpx` library is not integrated yet.
- The placeholder package preserves the source marker DOCX for debugging, including any `¡` markers.

Prevention:

- Keep placeholder metadata explicit until the real `pdf2hwpx` library is wired and validated.
- Validate the real library with marker DOCX samples before replacing the placeholder implementation.

## HWPX rhwp/H2O dependencies are not available in the current local session

Branch:

```text
feat/hwpx-rhwp-pipeline
```

Observed:

- `python3` is available.
- `rhwp` import fails with `ModuleNotFoundError`.
- `soffice` and `libreoffice` were not found in PATH during the local dependency check.
- Host tests, service smoke, local HWPX stub smoke, image build, and image smoke passed without those dependencies.

Known limitations:

- `hwpx-worker` currently uses a zip/XML local stub, not real `rhwp`.
- `libreoffice-worker --consume-hwpx-export` writes placeholder DOCX/PDF artifacts when `HWPX_H2O_EXPORT_ENABLED=false`.
- Setting `HWPX_H2O_EXPORT_ENABLED=true` fails explicitly because the real H2O export path is not implemented yet.

Prevention:

- Keep `HWPX_RHWP_ENABLED=false` and `HWPX_H2O_EXPORT_ENABLED=false` in local values until the real libraries are installed and validated.
- Validate real `rhwp` with representative HWPX files before replacing the stub location contract.
- Validate LibreOffice H2O/HWPX read/export support before marking HWPX final DOCX/PDF as production-ready.

## Docker Desktop command fails in WSL 1 distro

Commands:

```bash
docker version
docker ps
scripts/dev/check-env.sh
```

Observed error:

```text
The command 'docker' could not be found in this WSL 1 distro.
We recommend to convert this distro to WSL 2 and activate
the WSL integration in Docker Desktop settings.
```

Current PC evidence:

- `wsl.exe -l -v` reports `Ubuntu-18.04` as WSL `VERSION 1`.
- Docker Desktop's `docker-desktop` and `docker-desktop-data` distros are WSL `VERSION 2`.
- `command -v docker` resolves to Docker Desktop's Windows-side helper path, but the helper refuses to run from this WSL 1 distro.

Root cause:

- Docker Desktop WSL integration requires the active Linux distro to run as WSL 2.

Fix:

Run from Windows PowerShell:

```powershell
wsl --shutdown
wsl --set-version Ubuntu-18.04 2
wsl -l -v
```

Then enable Docker Desktop WSL integration for `Ubuntu-18.04`, reopen the distro, and verify:

```bash
docker version
docker ps
scripts/dev/check-env.sh
```

Prevention:

- At the start of a new PC/session, run `wsl.exe -l -v` and confirm the active project distro is WSL `VERSION 2` before running Docker or k3d validation.

## kubectl, Helm, and k3d missing on current PC

Commands:

```bash
kubectl version --client
helm version
k3d version
scripts/dev/check-env.sh
```

Observed:

- `kubectl`, `helm`, and `k3d` are not found in PATH.
- `$HOME/.local/bin` exists but does not contain Helm or k3d on this PC.

Root cause:

- The previously recorded Helm/k3d installation was from another local environment; this Ubuntu 18.04 distro does not currently have those tools installed.

Fix:

```bash
curl -fsSL -o /tmp/get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 /tmp/get_helm.sh
HELM_INSTALL_DIR="$HOME/.local/bin" /tmp/get_helm.sh --no-sudo

curl -fsSL -o /tmp/install_k3d.sh https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh
K3D_INSTALL_DIR="$HOME/.local/bin" bash /tmp/install_k3d.sh --no-sudo

export PATH="$HOME/.local/bin:$PATH"
helm version
k3d version
```

Install or restore `kubectl` for the distro, then rerun:

```bash
scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
```

Prevention:

- Do not assume `~/.local/bin` contents are portable across PCs or WSL distros.
- Keep `scripts/dev/check-env.sh` as the first local cluster command in every continuation.

## python3 points to Python 3.6 on current PC

Commands:

```bash
python3 --version
python3 -m compileall -q services tests
python3 -m unittest discover -s tests
scripts/dev/smoke-services.sh
```

Observed:

- `python3 --version` reports Python `3.6.9`.
- Compile and unit tests fail because Python 3.6 does not support `from __future__ import annotations`.
- `scripts/dev/smoke-services.sh` fails for the same reason when it uses its default `PYTHON_BIN=python3`.

Current workaround:

```bash
python3.10 -m compileall -q services tests
python3.10 -m unittest discover -s tests
PYTHON_BIN=python3.10 scripts/dev/smoke-services.sh
PYTHON_BIN=python3.10 scripts/dev/smoke-hwpx-local.sh
```

Result:

- All four commands passed on 2026-06-11 22:38 KST.

Fix:

- Prefer a project Python 3.10+ interpreter or virtual environment for host validation.
- On this Ubuntu 18.04 distro, keep using explicit `python3.10` / `PYTHON_BIN=python3.10` unless the distro's default `python3` is safely upgraded.

Prevention:

- Record Python version at the start of each PC bootstrap.
- Do not rely on `python3` being new enough on older Ubuntu distributions.

## Ubuntu 24.04 WSL install is not available from current WSL command list

Command:

```bash
/mnt/c/Windows/System32/wsl.exe --install Ubuntu-24.04 --no-launch --web-download
```

Observed error:

```text
Invalid distribution name: 'Ubuntu-24.04'
Error code: Wsl/InstallDistro/WSL_E_DISTRO_NOT_FOUND
```

Additional observation:

- `/mnt/c/Windows/System32/wsl.exe --list --online` lists generic `Ubuntu`, but not `Ubuntu-24.04`.
- The generic `Ubuntu` install command with `--no-launch --web-download` produced no output for over two minutes and did not register a new distro.

Root cause:

- This WSL installation does not expose `Ubuntu-24.04` as a direct installable distro name through the CLI.
- The generic web-download install path did not complete from the current Ubuntu 18.04 WSL1 session.

Fix:

- Install Ubuntu 24.04 from Windows using the Microsoft Store, App Installer, or another approved Windows-side WSL installation path.
- Confirm with:

```powershell
wsl -l -v
```

- The target distro must show WSL `VERSION 2`.

Prevention:

- Verify available distro names with `wsl --list --online` before scripting a specific Ubuntu version.
- Do not continue project validation from Ubuntu 18.04 WSL1 when the target recovery environment is Ubuntu 24.04 WSL2.

## Docker Desktop WSL integration is unstable in Ubuntu 24.04

Commands:

```bash
docker version
docker ps
curl --unix-socket /var/run/docker.sock http://localhost/_ping
```

Observed:

- `docker version` and `docker ps` passed once after starting Docker Desktop from Windows.
- Later, `/usr/bin/docker`, which points to `/mnt/wsl/docker-desktop/cli-tools/usr/bin/docker`, segfaulted.
- The Docker socket stopped responding to `_ping`.
- `wsl -l -v` did not show `docker-desktop` running at the point Docker commands failed.

Root cause:

- Docker Desktop is installed, but its WSL backend/integration is not stable or not fully enabled for `Ubuntu-24.04`.

Fix:

- Open Docker Desktop on Windows.
- Confirm Docker Desktop reports the engine as running.
- Open Settings -> Resources -> WSL Integration.
- Enable integration with `Ubuntu-24.04`.
- Apply & Restart Docker Desktop.
- In Ubuntu 24.04, rerun:

```bash
docker version
docker ps
curl --unix-socket /var/run/docker.sock http://localhost/_ping
```

Prevention:

- Treat one successful `docker ps` during Docker Desktop startup as insufficient; rerun `docker ps` after tool installs and before image builds.
- Do not proceed to k3d, image smoke, or live RabbitMQ/MinIO smoke while the Docker socket is unstable.

## Docker Desktop WSL integration recovered in Ubuntu 24.04

Commands:

```bash
docker version
docker ps
curl --unix-socket /var/run/docker.sock http://localhost/_ping
scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
```

Observed:

- The repo is now running from `Ubuntu-24.04` WSL2.
- Docker Desktop client/server `24.0.6` is reachable from Ubuntu 24.04.
- The Docker socket returns `OK`.
- `scripts/dev/check-env.sh` passes after cluster bootstrap with only optional warnings for missing kind/native k3s.
- k3d cluster `file-translation-dev` was created successfully and kubectl context is `k3d-file-translation-dev`.

Fix applied:

- User completed the Windows/WSL-side recovery and Docker Desktop WSL integration for Ubuntu 24.04.
- No sudo-based package repair was needed during the successful retry.
- Helm `v3.21.0` and k3d `v5.9.0` were already available in `/home/peto/.local/bin`.

Prevention:

- Before image or live smoke work, run `docker ps` and Docker socket `_ping`, not only `docker version`.
- If no k3d cluster exists, run `scripts/dev/bootstrap-cluster.sh` instead of assuming a stale kubectl context.
- Keep MinIO/RabbitMQ live smoke disposable until the Helm/local-stack path is implemented.

## PostgreSQL live validation is disposable only

Observed:

- No repository script currently deploys or validates a project-owned PostgreSQL service.
- The current validation used `postgres:16-alpine`, `pg_isready`, and `select 1` in a disposable Docker container.

Impact:

- Local PostgreSQL server accessibility is confirmed on this PC.
- Job-service persistence/outbox behavior remains unimplemented and unvalidated.

Prevention:

- Do not treat the disposable PostgreSQL smoke as proof of application persistence.
- Add a dedicated project smoke once PostgreSQL persistence or a local stack is implemented.

## job-service PostgreSQL repository live smoke added

Observed:

- `job-service` previously used only `InMemoryJobRepository`.
- That made RabbitMQ orchestration smoke possible, but not PostgreSQL state-update validation.

Fix:

- Added `JOB_SERVICE_REPOSITORY=postgres`.
- Added a minimal PostgreSQL repository that stores each job aggregate as JSONB in a `jobs` table.
- Added `scripts/dev/smoke-job-orchestration-live.sh`.
- The smoke runs disposable MinIO, RabbitMQ, PostgreSQL, and `job-service`.
- It verifies PostgreSQL state updates, RabbitMQ event consumption, next command publishing, and cancelled-job no-publish behavior.

Current limits:

- This is not the final normalized PostgreSQL schema.
- There is no outbox table yet.
- Helm/local-stack deployment of PostgreSQL is still pending.

Prevention:

- Keep `JOB_SERVICE_REPOSITORY=memory` as the default for host-side tests.
- Use `JOB_SERVICE_REPOSITORY=postgres` only when PostgreSQL is available.
- Do not treat the JSONB smoke table as the final persistence design.

## HWPX replace/export live smoke uses pre-uploaded input keys

Observed:

- `scripts/dev/smoke-hwpx-replace-export-live.sh` creates an HWPX job through `job-service` with a pre-uploaded MinIO input artifact.
- The initial `hwpx_extract` command must include `input_object_key`; otherwise `hwpx-worker --consume-extract` falls back to `{object_prefix}/input/original.hwpx` and may not read the seeded fixed input key.
- `hwpx_replace` defaults to `{object_prefix}/input/original.hwpx` for the original HWPX input.

Fix applied:

- `job-service` now adds `input_object_key` to the first route command when the job has an input key.
- The live smoke creates the job before starting workers, then copies the sample HWPX to the dynamic `{object_prefix}/input/original.hwpx` location before any worker can consume the initial command.
- This keeps the RabbitMQ contract additive and avoids changing worker next-queue behavior.

If the smoke fails near `hwpx_extract` input download:

```bash
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
scripts/dev/smoke-hwpx-replace-export-live.sh
```

Likely cause:

- The local `petoo/file-translation-job-service:0.1.0` image is stale and does not include the initial-command `input_object_key` publisher update.

Current limits:

- This smoke intentionally validates placeholder artifacts only.
- It does not enable real `rhwp` parsing or LibreOffice H2O export.
- It stops at `current_stage=email_send`; email delivery remains outside this smoke.

Prevention:

- Rebuild local images after job-service command contract changes.
- Keep pre-uploaded input-key tests in live smoke coverage so direct-upload jobs do not silently regress.
- Do not add worker-side next-command publishing to compensate for orchestration failures; job-service remains the component that publishes next commands.

## email_send end-state live smoke waits for job-service readiness

Observed:

- `scripts/dev/smoke-email-end-state-live.sh` initially failed while `job-service` was not yet serving `/readyz`.
- One failed iteration also revealed a script wiring error where the `job-service` container was missing `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`, causing it to wait on default `postgresql` settings.
- Disposable Docker networks can briefly report PostgreSQL as ready from the container itself before a new service container can resolve/connect to the `postgres` network alias.

Fix applied:

- Restored all `POSTGRES_*` environment variables on the `job-service` container in the smoke script.
- Added a same-network PostgreSQL DNS/connectivity check before starting `job-service`.
- Added an explicit `/readyz` wait before starting the email worker and driver.
- Added a bounded retry around PostgreSQL JSONB schema initialization in `PostgresJobRepository`.

If the smoke fails before `email-worker` starts:

```bash
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
scripts/dev/smoke-email-end-state-live.sh
```

Likely causes:

- The local `petoo/file-translation-job-service:0.1.0` image is stale and does not include the PostgreSQL startup retry.
- The script was edited and lost required `POSTGRES_*` environment variables.
- Docker Desktop's WSL networking is temporarily unstable.

Prevention:

- Keep `scripts/dev/smoke-email-end-state-live.sh` as a disposable live smoke, not a Helm substitute.
- Rebuild images after `job-service` repository/startup changes.
- Confirm `scripts/dev/check-env.sh` and `docker ps` pass before rerunning live smokes.

## HWPX route E2E smoke command queues must be clean before workers start

Observed:

- `scripts/dev/smoke-hwpx-route-e2e.sh` verifies cancellation gates before starting route workers, then purges command/event queues before creating the successful E2E job.
- The HWPX replacement worker still defaults to `{object_prefix}/input/original.hwpx`, so the E2E smoke copies the sample HWPX to the dynamic object prefix before workers can consume the initial command.
- A successful E2E run requires `job-service` to serve `/readyz` before workers and driver logic start.

Fix/behavior in the smoke:

- Start disposable MinIO, RabbitMQ, PostgreSQL, and `job-service`.
- Wait for PostgreSQL connectivity from the smoke network and for `job-service /readyz`.
- Run cancellation checks before workers start.
- Purge all command/event queues after cancellation checks.
- Create the main HWPX job, seed the dynamic input key, then start workers.
- After terminal completion, verify RabbitMQ command queues are empty.

If the smoke fails before worker startup:

```bash
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-hwpx-route-e2e.sh
```

Likely causes:

- Stale local images.
- Docker Desktop WSL networking instability.
- Missing or stale `POSTGRES_*`, RabbitMQ, or MinIO environment variables in the script.

Current limits:

- This is a Docker disposable E2E smoke, not a Helm deployment.
- It validates placeholder HWPX and mock email only.
- DOCX and PDF route-level E2E smokes are still separate follow-up work.

## DOCX route E2E smoke dynamic input and queue drain

Observed:

- `scripts/dev/smoke-docx-route-e2e.sh` creates the DOCX job with an explicit fixed `input_object_key`.
- Later `docx_replace` defaults to `{object_prefix}/input/original.docx`, so the E2E smoke also copies the sample DOCX to the dynamic object prefix before workers start.
- The route includes both `docx_marker` and `pdf2hwpx` before `email_send`.

Fix/behavior in the smoke:

- Start disposable MinIO, RabbitMQ, PostgreSQL, and `job-service`.
- Wait for PostgreSQL connectivity from the smoke network and for `job-service /readyz`.
- Run cancellation checks before route workers start.
- Purge all command/event queues after cancellation checks.
- Create the main DOCX job, seed the dynamic input key, then start workers.
- After terminal completion, verify final DOCX/PDF, marker DOCX, placeholder HWPX, email report, PostgreSQL JSONB state, and empty RabbitMQ command queues.

If the smoke fails near `docx_replace` input download:

```bash
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-docx-route-e2e.sh
```

Likely causes:

- The dynamic `{object_prefix}/input/original.docx` object was not seeded before workers started.
- Local images are stale.
- Docker Desktop WSL networking is unstable.

Current limits:

- DOCX extraction/replacement covers the current `word/document.xml` MVP only.
- DOCX PDF export and `pdf2hwpx` remain placeholder paths.
- This is a Docker disposable E2E smoke, not a Helm deployment.

## PDF route E2E smoke must start with static anchored pdf2docx

Observed:

- `scripts/dev/smoke-pdf-route-e2e.sh` must prove the PDF route starts with `pdf2docx`, not with `docx_extract`.
- The sample PDF and the worker conversion both use the custom static anchored image path.
- The downstream DOCX-route workers consume only after `job-service` receives the `pdf2docx stage.completed` event.

Fix/behavior in the smoke:

- Generate `sample.pdf` with `petoo/pdf2docx:0.5.13-py311-static`.
- Seed the PDF input object in MinIO.
- Start `pdf2docx-worker` with `PDF2DOCX_ENABLE_REPORTS=true`.
- Verify `01_pdf2docx/converted.docx`, `reports/pdf2docx.report.json`, and `reports/pdf2docx.report.md`.
- Continue through `docx_extract`, `docx_translate`, `docx_replace`, `docx_export`, `docx_marker`, `pdf2hwpx`, and `email_send`.
- Verify PostgreSQL JSONB terminal state, empty RabbitMQ command queues, and cancellation gates.

If the smoke fails before `docx_extract`:

```bash
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-pdf2docx-live.sh
scripts/dev/smoke-pdf-route-e2e.sh
```

Likely causes:

- The local `petoo/file-translation-pdf2docx-worker:0.1.0` image is stale or no longer based on `petoo/pdf2docx:0.5.13-py311-static`.
- `PDF2DOCX_ENABLE_REPORTS=true` was removed, so report artifacts are missing.
- The initial command did not carry the uploaded `input_object_key`.
- Docker Desktop WSL networking is unstable.

Current limits:

- The smoke uses the converter's local sample PDF, not a broad PDF corpus.
- DOCX export and `pdf2hwpx` remain placeholder paths.
- This is a Docker disposable E2E smoke, not a Helm deployment.

## PostgreSQL readiness checks in disposable live smokes

Observed:

- During DOCX E2E validation, `scripts/dev/smoke-hwpx-replace-export-live.sh` failed twice at PostgreSQL readiness before worker startup.
- A preserved-container rerun passed, indicating a readiness timing issue rather than a MinIO/RabbitMQ/job-service contract failure.

Fix applied:

- `scripts/dev/smoke-hwpx-replace-export-live.sh` now records an explicit `postgres_ready=1` flag inside the wait loop and only fails if the flag never becomes true.
- `scripts/dev/smoke-job-orchestration-live.sh` now uses the same flag pattern.
- Newer route-level E2E smokes already include this pattern plus same-network PostgreSQL connectivity checks where needed.

If a PostgreSQL readiness failure appears again:

```bash
KEEP_LIVE_SMOKE=1 scripts/dev/smoke-hwpx-replace-export-live.sh
docker logs ft-hwpx-replace-export-postgres-live
docker ps -a --filter name=ft-hwpx-replace-export
```

Then clean up the preserved stack:

```bash
docker rm -f \
  ft-hwpx-replace-export-db-check-live \
  ft-hwpx-replace-export-verify-live \
  ft-hwpx-replace-export-setup-live \
  ft-hwpx-replace-export-cancel-live \
  ft-hwpx-replace-export-seed-live \
  ft-hwpx-replace-export-export-live \
  ft-hwpx-replace-export-translate-live \
  ft-hwpx-replace-export-replace-live \
  ft-hwpx-replace-export-extract-live \
  ft-hwpx-replace-export-job-service-live \
  ft-hwpx-replace-export-postgres-live \
  ft-hwpx-replace-export-rabbitmq-live \
  ft-hwpx-replace-export-minio-live
docker network rm ft-hwpx-replace-export-live
```

## Frontend or Admin UI tries to publish RabbitMQ messages

Observed:

- A frontend, admin UI, or user integration asks for RabbitMQ credentials.
- A client attempts to publish directly to `q.commands.*`.
- Operators consider fixing a stuck job by manually publishing a command from outside `job-service`.

Required behavior:

- Do not expose RabbitMQ as a public API.
- Route all user/admin actions through `job-service`.
- Use `POST /jobs` to start work.
- Use `POST /jobs/{job_id}/cancel` to cancel work.
- Use the future `POST /jobs/{job_id}/retry` API for retries.

Reason:

- `job-service` owns PostgreSQL job state, cancellation gates, route selection, and next-stage orchestration.
- Direct external queue publish can desynchronize PostgreSQL state from worker commands.
- Direct external queue publish can bypass no-send cancellation checks.

Reference:

```text
docs/API.md
docs/USAGE.md
docs/ADMIN_UI.md
docs/CONTRACTS.md
```

## External RabbitMQ queues are missing

Observed:

- Workers start but do not receive commands.
- `job-service` fails to publish a command.
- RabbitMQ management UI does not show one or more required queues.

Required queues:

```text
q.commands.pdf2docx
q.commands.docx_extract
q.commands.docx_translate
q.commands.docx_replace
q.commands.docx_export
q.commands.docx_marker
q.commands.pdf2hwpx
q.commands.hwpx_extract
q.commands.hwpx_translate
q.commands.hwpx_replace
q.commands.hwpx_export
q.commands.email_send
q.events.stage_completed
q.events.stage_failed
q.events.progress
```

Fix:

- For local Docker smokes, rerun the smoke script; the Python RabbitMQ helpers declare queues before use.
- For Helm/closed-network deployment, run the future queue initialization Job.
- The queue initialization Job must be idempotent and should treat already existing queues as success.
- Check `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_VHOST`, `RABBITMQ_USERNAME`, `RABBITMQ_PASSWORD`, and `RABBITMQ_TLS_ENABLED`.

Reference:

```text
docs/CLOSED_NETWORK_DEPLOYMENT.md
docs/CONTRACTS.md
services/common/ft_common/config.py
```

## Upload flow is unclear for frontend integration

Observed:

- A frontend tries to construct MinIO object keys itself.
- A frontend asks for MinIO credentials.
- A frontend starts a job before the input object exists.

Fix:

- Choose one public upload mode per deployment:
  - job-service mediated multipart upload
  - job-service issued presigned upload URL
- Keep MinIO authorization under `job-service`.
- Start the route only after `job-service` can record the input artifact key in PostgreSQL.

Current smoke note:

- Route-level E2E smokes pre-seed MinIO and pass `input_object_key` to `POST /jobs`.
- This is a smoke harness shortcut, not a frontend API pattern.

## Admin API smoke fails

Observed:

- `scripts/dev/smoke-admin-api.sh` fails before readiness.
- `GET /admin/jobs` does not show expected completed/cancelled/failed jobs.
- `POST /jobs/{job_id}/retry` does not publish a retry command for a failed job.

Quick checks:

```bash
python3 -m compileall -q services tests
python3 -m unittest tests.test_job_service_api
PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh
```

Likely causes:

- Port `18081` is already in use. Override with `ADMIN_API_SMOKE_PORT=<port>`.
- `job-service` API routing changed without updating `scripts/dev/smoke-admin-api.sh`.
- The failed job has no `error_stage`, so retry is not allowed.
- A non-failed job was retried; this correctly returns `409 retry_not_allowed`.

Boundary reminder:

- The Admin UI and smoke call `job-service` APIs only.
- They do not publish RabbitMQ messages directly.

## Long-running stage command is redelivered or duplicated

Observed:

- Large PDF/HWPX/DOCX jobs rerun the same stage.
- RabbitMQ shows unacked command messages for a long time.
- A worker logs connection lost, heartbeat timeout, or channel closure during conversion/export.
- A downstream command is published twice after the same `stage.completed` event is seen twice.

Pre-MVP root cause:

- Worker RabbitMQ command consumers ack after the handler returns.
- Long-running handlers keep the command unacked until conversion/export, MinIO upload, and event publish complete.
- Workers do not claim a stage through `job-service` before work.
- `job-service` does not yet reject duplicate in-route completed events with an attempt/claim/idempotency check.

Current MVP behavior:

- Job-service-created commands include `command_id`.
- Workers claim the stage through `job-service` before work.
- Workers ack RabbitMQ after durable `CLAIMED` or no-op.
- Workers heartbeat while processing.
- Duplicate running/completed/cancelled/max-attempt commands no-op or fail safely through claim status.
- Duplicate/stale completed events do not publish duplicate downstream commands.

Claim statuses:

```text
CLAIMED
ALREADY_COMPLETED
ALREADY_RUNNING
JOB_CANCELLED
MAX_ATTEMPTS_EXCEEDED
INVALID_STAGE
```

Immediate response:

```bash
GET /jobs/{job_id}
GET /jobs/{job_id}/stages
GET /jobs/{job_id}/artifacts
GET /admin/jobs/{job_id}
```

Then inspect the current stage fields:

```text
attempt
max_attempts
command_id
claim_id
lease_until
last_heartbeat_at
progress
long_running
last_error
```

Do not manually publish RabbitMQ commands from frontend/admin/user tooling.

Remaining follow-up:

- Add stale lease sweeper/reconciler.
- Add delayed retry/backoff and `next_retry_at`.
- Treat direct legacy RabbitMQ commands without `command_id` as developer-smoke-only, not production-safe.

## Duplicate email send risk

Observed:

- Two `email_send` commands are delivered while the job is still `running/current_stage=email_send`.
- The first provider call succeeds, but the completion event is delayed or lost.
- The provider receives duplicate send requests.

Pre-MVP root cause:

- `email-worker` correctly calls `GET /jobs/{job_id}/sendability`, but sendability is true until job-service processes `email_send stage.completed`.
- There is no email-send claim, provider idempotency key, or persisted send-in-progress state.

Current MVP behavior:

- `email-worker` claims `email_send` through job-service before provider call when the command was created by job-service.
- Duplicate running `email_send` commands return `ALREADY_RUNNING`.
- Completed `email_send` commands return `ALREADY_COMPLETED`.
- Cancelled/cancel-requested jobs return `JOB_CANCELLED` or fail sendability before provider call.

Remaining follow-up:

- Require provider idempotency key when the military/internal API supports it.
- Record provider message id and `email_report` before allowing duplicate commands to no-op safely.

Reference:

```text
docs/RELIABILITY_REPLAN.md
docs/REPLACEMENT_GUIDE.md
```
