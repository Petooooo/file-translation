# Validation

Last updated: 2026-06-13 00:40 KST

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

- No Helm chart exists yet.
- No MinIO, RabbitMQ, or PostgreSQL instance has been deployed yet.
- Phase 2 services are skeletons only; they do not connect to RabbitMQ, MinIO, or PostgreSQL yet.

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

## Phase 1 Initial Blocker

This blocker was resolved on 2026-06-09 23:52 KST. Historical install commands used:

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh

curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

scripts/dev/check-env.sh
scripts/dev/bootstrap-cluster.sh
scripts/dev/smoke-test.sh
```

## Phase 1 Blocker Resolution Commands

| Command | Result |
| --- | --- |
| `sudo -n true` | Failed: password required; avoided system-wide install. |
| `HELM_INSTALL_DIR="$HOME/.local/bin" /tmp/get_helm.sh --no-sudo` | Installed Helm binary; official script returned non-zero because zsh PATH did not include `~/.local/bin`. |
| `PATH="$HOME/.local/bin:$PATH" helm version --short` | Passed: `v4.2.0+g0646808`. |
| `PATH="$HOME/.local/bin:$PATH" K3D_INSTALL_DIR="$HOME/.local/bin" /tmp/install_k3d.sh --no-sudo` | Passed. |
| `PATH="$HOME/.local/bin:$PATH" k3d version` | Passed: k3d `v5.9.0`; k3d default k3s line is `v1.35.5-k3s1`. |
| `docker manifest inspect rancher/k3s:v1.32.13-k3s1` | Passed after one retry. |
| `scripts/dev/check-env.sh` | Passed after install; Helm and k3d detected; existing Docker Desktop API warning remained before k3d context was created. |
| `scripts/dev/bootstrap-cluster.sh` | Passed; created `file-translation-dev` with k3s `v1.32.13+k3s1` and namespace `file-translation`. |
| `scripts/dev/smoke-test.sh` | Passed; nodes Ready, namespace exists, CoreDNS exists, busybox DNS lookup succeeded. |
| `scripts/dev/check-env.sh` | Passed after cluster creation; Kubernetes API reachable on context `k3d-file-translation-dev`. |

## Phase 1 Resolved Local State

- Helm `v4.2.0` installed at `/home/peto/.local/bin/helm`.
- k3d `v5.9.0` installed at `/home/peto/.local/bin/k3d`.
- Project scripts prepend `~/.local/bin` to PATH when it exists.
- Current kubectl context: `k3d-file-translation-dev`.
- Nodes:
  - `k3d-file-translation-dev-server-0`: Ready, k3s `v1.32.13+k3s1`.
  - `k3d-file-translation-dev-agent-0`: Ready, k3s `v1.32.13+k3s1`.
- Namespace `file-translation` is Active.
- Cluster DNS resolved `kubernetes.default.svc.cluster.local` to `10.43.0.1` from a temporary busybox pod.

## Phase 2 Commands

| Command | Result |
| --- | --- |
| `python3 --version` | Python `3.10.12` used for host-side tests. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 11 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `scripts/dev/build-images.sh` | Passed: all 8 images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed: all 8 image smoke commands. |
| `docker image inspect ...` | Passed; local image IDs recorded in `docs/IMAGE_INVENTORY.md`. |
| `docker push petoo/file-translation-job-service:0.1.0` | Failed: `denied: requested access to the resource is denied`; no images were pushed. |
| `git diff --check` | Passed before commit. |

## Phase 2 Validation Summary

- `job-service` has `/healthz`, `/readyz`, and `/config` handlers covered by tests.
- All workers have smoke commands and long-running no-op container entrypoints.
- Config loading is environment-driven and excludes secret values from safe output.
- MinIO object key convention is implemented as pure helper functions and covered by tests.
- Docker images use namespace `petoo` and explicit tag `0.1.0`.
- Registry digests are not available because Docker Hub push was denied.

## 2026-06-10 Pipeline Replan Validation

| Command | Result |
| --- | --- |
| `git status --short --branch` | On `docs/pipeline-replan`; worktree had docs replan edits in progress. |
| `git branch --all --verbose --no-abbrev` | Existing branches: `main`, `codex/plan-bootstrap-local-k8s`, `codex/feat-skeleton-services`, `docs/pipeline-replan`. |
| `git log --oneline --decorate --graph --max-count=20` | Replan branch created from `bb635ab` preserving Phase 1 and Phase 2 work. |
| `rg --files` | Confirmed existing docs, scripts, service skeletons, and tests are present. |
| `scripts/dev/check-env.sh` | Failed in current session: Docker server not reachable, `kubectl` not found in PATH; Helm/k3d still detected. |
| `docker --version` | Failed: Docker command unavailable in this WSL distro; Docker Desktop WSL integration likely disabled. |
| `docker info` | Failed for same Docker availability reason. |
| `command -v kubectl && kubectl version --client` | Failed: `kubectl` not found in PATH. |
| `rg -n "26-01-03|\{yy|q\.commands\.extract|q\.commands\.translate|q\.commands\.replace|q\.commands\.libreoffice" docs tests services scripts` | Passed for active contracts; only obsolete-format notes remain. |
| `python3 -m unittest discover -s tests` | Passed: 12 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |

## Custom pdf2docx Image Validation Status

Required commands:

```bash
docker pull petoo/pdf2docx:0.5.13-py311-static
docker run --rm petoo/pdf2docx:0.5.13-py311-static \
  python -m pdf2docx.static_anchored.cli --help
mkdir -p out
docker run --rm \
  -v "$PWD/out:/work/out" \
  petoo/pdf2docx:0.5.13-py311-static \
  python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out --with-report
```

Current result:

- Not run in this session because Docker is unavailable.
- Run these commands after Docker Desktop WSL integration or Docker daemon access is restored.
- Expected smoke files are listed in `docs/LOCAL_DEV_SETUP.md`.

## 2026-06-10 Job-service Input Routing Validation

Branch: `feat/job-service-input-routing`

Implementation commit: `3934cf3`

| Command | Result |
| --- | --- |
| `git branch --show-current` | Passed: `feat/job-service-input-routing`. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 21 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |

Covered by tests:

- `input_type=pdf` starts at `pdf2docx`.
- `input_type=docx` starts at `docx_extract` and skips `pdf2docx`.
- `input_type=hwpx` starts at `hwpx_extract` and stays on the HWPX route.
- Invalid `input_type` is rejected.
- `stage.completed` events publish only the next route stage through `job-service`.
- `cancel_requested` jobs do not publish the next command and move to `cancelled` after the in-flight stage event.
- Job query payloads expose current status, current stage, artifacts, and progress.
- Completing `email_send` marks the job `completed`.

Notes:

- Docker, kubectl, and cluster validation were not required for this job-service-only branch.
- The existing Docker/kubectl availability blocker from the pipeline replan remains until the local environment is restored.

## 2026-06-10 RabbitMQ Orchestration Adapter Validation

Branch: `feat/rabbitmq-orchestration`

Implementation commit: `1d3caed`

| Command | Result |
| --- | --- |
| `git branch --show-current` | Passed: `feat/rabbitmq-orchestration`. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 28 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |

Covered by tests:

- `JOB_SERVICE_COMMAND_PUBLISHER=memory` selects the in-memory publisher.
- `JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq` selects the RabbitMQ publisher without connecting until publish time.
- RabbitMQ command publishing declares the target command queue durable and publishes the expected JSON command body.
- RabbitMQ event queues map to `q.events.stage_completed`, `q.events.stage_failed`, and `q.events.progress`.
- RabbitMQ event consumer dispatches valid events into `job-service` and acks them.
- Bad event bodies are nacked with `requeue=false`.
- Host-side smoke commands still run without RabbitMQ.

Not run:

- Docker image rebuild/smoke for the new `pika` dependency was not run because the current session still lacks Docker access.
- Live RabbitMQ integration was not run because no broker is available in the current session.

## 2026-06-10 Local Environment and Image Validation Resumed

Branch: `feat/rabbitmq-orchestration`

| Command | Result |
| --- | --- |
| `scripts/dev/check-env.sh` | Passed; Docker server, kubectl, Helm, k3d, current context, and Kubernetes API reachable. |
| `scripts/dev/smoke-test.sh` | Passed; k3d nodes Ready, namespace `file-translation` exists, CoreDNS exists, DNS lookup succeeds. |
| `kubectl get nodes -o wide` | Passed; `k3d-file-translation-dev-server-0` and `k3d-file-translation-dev-agent-0` Ready on k3s `v1.32.13+k3s1`. |
| `kubectl get namespace file-translation` | Passed; namespace is Active. |
| `scripts/dev/build-images.sh` | Passed; all 8 `petoo/file-translation-*` images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `docker info ... Username` | No Docker Hub username reported; image push not attempted. |
| `docker pull petoo/pdf2docx:0.5.13-py311-static` | Passed; registry digest `sha256:d3ef804baceed3516e8ce89df3a33abfde00c1fd348541c3b8ad0cb9fc404f0f`. |
| `docker run --rm petoo/pdf2docx:0.5.13-py311-static python -m pdf2docx.static_anchored.cli --help` | Passed; expected CLI flags are present. |
| `docker run --rm -v "$PWD/out:/work/out" petoo/pdf2docx:0.5.13-py311-static python /opt/pdf2docx/examples/static_anchored_smoke.py --out-dir /work/out --with-report` | Passed; smoke status `converted`, validation counts are 0. |

Generated pdf2docx smoke files:

```text
out/sample.pdf
out/sample.static.docx
out/sample.static.report.json
out/sample.static.report.md
```

Notes:

- `out/` is ignored by Git because it contains local validation artifacts.
- Current service image IDs and the custom pdf2docx digest are recorded in `docs/IMAGE_INVENTORY.md`.
- Live RabbitMQ integration is still pending until a RabbitMQ broker is deployed or otherwise available.

## 2026-06-10 pdf2docx Static Worker Validation

Branch: `feat/pdf2docx-static-worker`

Implementation commit: `957830c`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 34 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |
| `scripts/dev/build-images.sh` | Passed; all 8 images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `docker run --rm petoo/file-translation-pdf2docx-worker:0.1.0 python -m pdf2docx.static_anchored.cli --help` | Passed; static anchored CLI is available inside the worker image. |
| `docker run --rm -v "$PWD/out/pdf2docx-worker:/work/out" petoo/file-translation-pdf2docx-worker:0.1.0 python /app/service/worker.py --convert-local --input /work/out/sample.pdf --output /work/out/worker.static.docx --with-report --overwrite` | Passed; worker returned `status=converted`. |

Generated worker validation files:

```text
out/pdf2docx-worker/sample.pdf
out/pdf2docx-worker/sample.static.docx
out/pdf2docx-worker/sample.static.report.json
out/pdf2docx-worker/sample.static.report.md
out/pdf2docx-worker/worker.static.docx
out/pdf2docx-worker/worker.static.report.json
out/pdf2docx-worker/worker.static.report.md
```

Covered by tests:

- `pdf2docx-worker` builds the required `python -m pdf2docx.static_anchored.cli` command.
- Optional report paths map to `*.report.json` and `*.report.md`.
- Non-PDF input paths fail fast.
- Fake conversion runner returns the expected artifact output keys: `converted_docx`, `pdf2docx_report_json`, and `pdf2docx_report_md`.
- `PDF2DOCX_IMAGE` defaults to `petoo/pdf2docx:0.5.13-py311-static`.
- `PDF2DOCX_ENABLE_REPORTS` is parsed as a boolean and fails fast on invalid values.

Still pending:

- RabbitMQ command consumption for worker commands.
- MinIO download/upload integration for real artifact keys.
- Worker event publishing to `q.events.stage_completed` / `q.events.stage_failed`.

## 2026-06-10 pdf2docx Worker Artifact/Event Validation

Branch: `feat/pdf2docx-worker-artifacts`

Implementation commit: `e539dc1`

| Command | Result |
| --- | --- |
| `python3 -m pip index versions minio` | Passed; selected `minio==7.2.20`. |
| `python3 -m pip index versions pika` | Passed; selected existing project pin `pika==1.3.2`. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 45 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |
| `scripts/dev/build-images.sh` | Passed; all 8 images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `docker run --rm -i petoo/file-translation-pdf2docx-worker:0.1.0 python - ...` | Passed; container reports `minio 7.2.20` and `pika 1.3.2`. |
| `docker run --rm -v "$PWD/out/pdf2docx-worker:/work/out" petoo/file-translation-pdf2docx-worker:0.1.0 python /app/service/worker.py --convert-local ...` | Passed; worker returned `status=converted`. |

Covered by tests:

- MinIO endpoint normalization for `http`, `https`, and bare endpoints.
- MinIO config uses `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` without leaking values through `safe_dict()`.
- MinIO store delegates download/upload to the client with the configured bucket and content type.
- RabbitMQ JSON publisher declares durable queues and publishes JSON.
- RabbitMQ JSON consumer ack/nack behavior is covered without a live broker.
- `pdf2docx-worker` validates `input_type=pdf` and `stage=pdf2docx`.
- Artifact keys follow `{YYYY-MM-DD}/{user_id}/{file_id}/...`.
- `pdf2docx-worker` produces `stage.completed` outputs for `converted_docx`, `pdf2docx_report_json`, and `pdf2docx_report_md`.
- `pdf2docx-worker` produces `stage.failed` event payloads on failure.

Follow-up completed on `test/pdf2docx-worker-live-smoke`:

- Live MinIO bucket/object smoke test.
- Live RabbitMQ command consumption and event publish smoke test.

Still pending:

- Helm/local stack deployment of RabbitMQ and MinIO for repeatable live validation.

## 2026-06-10 pdf2docx Live MinIO/RabbitMQ Smoke Validation

Branch: `test/pdf2docx-worker-live-smoke`

| Command | Result |
| --- | --- |
| `docker manifest inspect minio/minio:RELEASE.2025-02-07T23-21-09Z` | Passed. |
| `docker manifest inspect rabbitmq:3.13-management` | Passed. |
| `docker manifest inspect busybox:1.36` | Passed. |
| `bash -n scripts/dev/smoke-pdf2docx-live.sh` | Passed. |
| `scripts/dev/smoke-pdf2docx-live.sh` | Passed. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 45 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |

Live smoke behavior:

- Started disposable Docker network `ft-pdf2docx-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated `out/pdf2docx-live/sample.pdf` with `petoo/pdf2docx:0.5.13-py311-static`.
- Uploaded the sample PDF to `file-translation/2026-01-21/12345678/a8f3k2p9/input/original.pdf`.
- Ran `petoo/file-translation-pdf2docx-worker:0.1.0 python /app/service/worker.py --consume`.
- Published a command to `q.commands.pdf2docx`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified these MinIO objects exist:

```text
2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json
2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md
```

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "pdf",
  "job_id": "live-pdf2docx-smoke",
  "outputs": {
    "converted_docx": "2026-01-21/12345678/a8f3k2p9/01_pdf2docx/converted.docx",
    "pdf2docx_report_json": "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.json",
    "pdf2docx_report_md": "2026-01-21/12345678/a8f3k2p9/reports/pdf2docx.report.md"
  },
  "stage": "pdf2docx"
}
```

Remaining:

- Helm/local-stack deployment still needs to replace the ad hoc Docker smoke for repeatable Kubernetes validation.
- Downstream `docx_extract` handling was completed on `feat/pdf-docx-pipeline`; later stages still need implementation before a full PDF route can complete.

## 2026-06-10 docx_extract Worker Artifact/Event Validation

Branch: `feat/pdf-docx-pipeline`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 51 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `python3 services/docx-extract-worker/worker.py --extract-local ...` | Passed; generated `text_units.json` with 2 units. |
| `docker run --rm -v "$PWD/out/docx-extract-worker:/work/out" petoo/file-translation-docx-extract-worker:0.1.0 python /app/service/worker.py --extract-local ...` | Passed; generated `container.text_units.json` with 2 units. |
| `bash -n scripts/dev/smoke-docx-extract-live.sh` | Passed. |
| `scripts/dev/smoke-docx-extract-live.sh` | Passed. |

Covered by tests:

- DOCX extraction reads non-blank `w:t` nodes from `word/document.xml`.
- `text_units.json` includes `schema_version`, `job_id`, `input_type`, `source_lang`, `target_lang`, and unit locations.
- `docx-extract-worker` accepts `input_type=pdf` and `input_type=docx`.
- `docx-extract-worker` rejects `input_type=hwpx` and wrong stage names.
- PDF route input defaults to `{object_prefix}/01_pdf2docx/converted.docx`.
- DOCX route input defaults to `{object_prefix}/input/original.docx`.
- Optional `input_object_key` overrides the default input key.
- Worker event output uses `{object_prefix}/02_extract/text_units.json`.
- `stage.failed` events use `DOCX_EXTRACT_WORKER_FAILED`.

Live smoke behavior:

- Started disposable Docker network `ft-docx-extract-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated a minimal sample DOCX.
- Uploaded the sample DOCX to `file-translation/2026-01-21/12345678/docxsmoke1/input/original.docx`.
- Ran `petoo/file-translation-docx-extract-worker:0.1.0 python /app/service/worker.py --consume`.
- Published a command to `q.commands.docx_extract`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/docxsmoke1/02_extract/text_units.json` exists in MinIO and contains 2 text units.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-docx-extract-smoke",
  "outputs": {
    "text_units": "2026-01-21/12345678/docxsmoke1/02_extract/text_units.json"
  },
  "stage": "docx_extract"
}
```

Remaining:

- `docx_replace`, `docx_export`, `docx_marker`, and `pdf2hwpx` still need artifact/event implementations.

## 2026-06-10 docx_translate Worker Artifact/Event Validation

Branch: `feat/pdf-docx-pipeline`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 56 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `python3 services/translate-worker/worker.py --translate-local ...` | Passed; generated mock `translated_units.json` with 2 units. |
| `docker run --rm -v "$PWD/out/docx-translate-worker:/work/out" petoo/file-translation-translate-worker:0.1.0 python /app/service/worker.py --translate-local ...` | Passed; generated container `translated_units.json` with 2 units. |
| `bash -n scripts/dev/smoke-docx-translate-live.sh` | Passed. |
| `scripts/dev/smoke-docx-translate-live.sh` | Passed. |
| `git diff --check` | Passed. |

Covered by tests:

- Mock provider returns deterministic local translations without external API keys.
- `translated_units.json` includes `schema_version`, `job_id`, `input_type`, `source_lang`, `target_lang`, provider, and translated unit records.
- `translate-worker` accepts `input_type=pdf` and `input_type=docx` for `docx_translate`.
- `translate-worker` rejects `input_type=hwpx` and wrong stage names for the DOCX route.
- Input defaults to `{object_prefix}/02_extract/text_units.json`.
- Output defaults to `{object_prefix}/03_translate/translated_units.json`.
- Optional `input_object_key` and `output_object_key` override the defaults.
- Progress events use `event_type=translate.progress`.
- `stage.failed` events use `TRANSLATE_WORKER_FAILED`.

Live smoke behavior:

- Started disposable Docker network `ft-docx-translate-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated a sample `text_units.json`.
- Uploaded it to `file-translation/2026-01-21/12345678/translatesmoke1/02_extract/text_units.json`.
- Ran `petoo/file-translation-translate-worker:0.1.0 python /app/service/worker.py --consume` with `TRANSLATION_PROVIDER=mock`.
- Published a command to `q.commands.docx_translate`.
- Received at least one `translate.progress` event from `q.events.progress`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/translatesmoke1/03_translate/translated_units.json` exists in MinIO and contains mock translations.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-docx-translate-smoke",
  "outputs": {
    "translated_units": "2026-01-21/12345678/translatesmoke1/03_translate/translated_units.json"
  },
  "stage": "docx_translate"
}
```

Remaining:

- `docx_replace`, `docx_export`, `docx_marker`, and `pdf2hwpx` still need artifact/event implementations.
- HWPX `hwpx_translate` remains separate and is not implemented by this DOCX-route branch.

## 2026-06-10 docx_replace Worker Artifact/Event Validation

Branch: `feat/pdf-docx-pipeline`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 61 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `python3 services/docx-replace-worker/worker.py --replace-local ...` | Passed; replaced 2 sample DOCX text nodes. |
| `docker run --rm -v "$PWD/out/docx-replace-worker:/work/out" petoo/file-translation-docx-replace-worker:0.1.0 python /app/service/worker.py --replace-local ...` | Passed; replaced 2 sample DOCX text nodes. |
| `bash -n scripts/dev/smoke-docx-replace-live.sh` | Passed. |
| `scripts/dev/smoke-docx-replace-live.sh` | Passed. |
| `git diff --check` | Passed. |

Covered by tests:

- DOCX replacement reads `text_units.json` location metadata and `translated_units.json` translations by `uid`.
- `docx-replace-worker` accepts `input_type=pdf` and `input_type=docx`.
- `docx-replace-worker` rejects `input_type=hwpx` and wrong stage names for the DOCX route.
- PDF route input defaults to `{object_prefix}/01_pdf2docx/converted.docx`.
- DOCX route input defaults to `{object_prefix}/input/original.docx`.
- Text units default to `{object_prefix}/02_extract/text_units.json`.
- Translated units default to `{object_prefix}/03_translate/translated_units.json`.
- Output defaults to `{object_prefix}/04_replace/translated.docx`.
- Optional input/output object key overrides are honored.
- Worker completed output uses `translated_docx`.
- `stage.failed` events use `DOCX_REPLACE_WORKER_FAILED`.

Live smoke behavior:

- Started disposable Docker network `ft-docx-replace-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated a minimal sample DOCX plus matching `text_units.json` and `translated_units.json`.
- Uploaded inputs under `file-translation/2026-01-21/12345678/replacesmoke1`.
- Ran `petoo/file-translation-docx-replace-worker:0.1.0 python /app/service/worker.py --consume`.
- Published a command to `q.commands.docx_replace`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/replacesmoke1/04_replace/translated.docx` exists in MinIO and contains the mock translated text.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-docx-replace-smoke",
  "outputs": {
    "translated_docx": "2026-01-21/12345678/replacesmoke1/04_replace/translated.docx"
  },
  "stage": "docx_replace"
}
```

Remaining:

- `docx_export`, `docx_marker`, and `pdf2hwpx` still need artifact/event implementations.
- HWPX `hwpx_replace` remains separate and is not implemented by this DOCX-route branch.

## 2026-06-10 docx_export Worker Artifact/Event Validation

Branch: `feat/pdf-docx-pipeline`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 66 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `python3 services/libreoffice-worker/worker.py --export-local ...` | Passed; copied final DOCX and wrote placeholder PDF. |
| `docker run --rm -v "$PWD/out/docx-export-worker:/work/out" petoo/file-translation-libreoffice-worker:0.1.0 python /app/service/worker.py --export-local ...` | Passed; copied final DOCX and wrote placeholder PDF in container. |
| `bash -n scripts/dev/smoke-docx-export-live.sh` | Passed. |
| `scripts/dev/smoke-docx-export-live.sh` | Passed. |
| `git diff --check` | Passed. |

Covered by tests:

- `libreoffice-worker` accepts `input_type=pdf` and `input_type=docx`.
- `libreoffice-worker` rejects `input_type=hwpx` and wrong stage names for the DOCX route.
- Input defaults to `{object_prefix}/04_replace/translated.docx`.
- Final DOCX defaults to `{object_prefix}/05_export/final.docx`.
- Final PDF defaults to `{object_prefix}/05_export/final.pdf`.
- Optional input/final output object key overrides are honored.
- Worker completed output uses `final_docx` and `final_pdf`.
- `stage.failed` events use `DOCX_EXPORT_WORKER_FAILED`.
- Placeholder PDF output starts with a valid PDF header.

Live smoke behavior:

- Started disposable Docker network `ft-docx-export-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated a minimal translated DOCX.
- Uploaded it to `file-translation/2026-01-21/12345678/exportsmoke1/04_replace/translated.docx`.
- Ran `petoo/file-translation-libreoffice-worker:0.1.0 python /app/service/worker.py --consume` with `DOCX_EXPORT_PDF_MODE=placeholder`.
- Published a command to `q.commands.docx_export`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/exportsmoke1/05_export/final.docx` and `2026-01-21/12345678/exportsmoke1/05_export/final.pdf` exist in MinIO.
- Verified final DOCX text and placeholder PDF header after downloading artifacts.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-docx-export-smoke",
  "outputs": {
    "final_docx": "2026-01-21/12345678/exportsmoke1/05_export/final.docx",
    "final_pdf": "2026-01-21/12345678/exportsmoke1/05_export/final.pdf"
  },
  "stage": "docx_export"
}
```

Remaining:

- `docx_marker` and `pdf2hwpx` still need artifact/event implementations.
- Real LibreOffice PDF conversion is not validated yet; local default remains placeholder mode.
- HWPX `hwpx_export` remains separate and is not implemented by this DOCX-route branch.

## 2026-06-11 docx_marker Worker Artifact/Event Validation

Branch: `feat/pdf-docx-pipeline`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 71 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `python3 services/libreoffice-worker/worker.py --mark-local ...` | Passed; replaced spaces with `¡` in a sample DOCX. |
| `docker run --rm -v "$PWD/out/docx-marker-worker:/work/out" petoo/file-translation-libreoffice-worker:0.1.0 python /app/service/worker.py --mark-local ...` | Passed; replaced spaces with `¡` in container. |
| `bash -n scripts/dev/smoke-docx-marker-live.sh` | Passed. |
| `scripts/dev/smoke-docx-marker-live.sh` | Passed. |
| `git diff --check` | Passed. |

Covered by tests:

- `libreoffice-worker --consume-marker` accepts `input_type=pdf` and `input_type=docx`.
- It rejects `input_type=hwpx` and wrong stage names for the DOCX marker route.
- Input defaults to `{object_prefix}/05_export/final.docx`.
- Marker DOCX defaults to `{object_prefix}/05_export/marker.docx`.
- Optional input and marker object key overrides are honored.
- Worker completed output uses `marker_docx`.
- `stage.failed` events use `DOCX_MARKER_WORKER_FAILED`.
- DOCX marker generation replaces spaces in `word/*.xml` `w:t` text nodes.

Live smoke behavior:

- Started disposable Docker network `ft-docx-marker-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated a minimal final DOCX.
- Uploaded it to `file-translation/2026-01-21/12345678/markersmoke1/05_export/final.docx`.
- Ran `petoo/file-translation-libreoffice-worker:0.1.0 python /app/service/worker.py --consume-marker`.
- Published a command to `q.commands.docx_marker`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/markersmoke1/05_export/marker.docx` exists in MinIO.
- Verified downloaded marker DOCX text nodes contain `¡` instead of spaces.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-docx-marker-smoke",
  "outputs": {
    "marker_docx": "2026-01-21/12345678/markersmoke1/05_export/marker.docx"
  },
  "stage": "docx_marker"
}
```

Remaining:

- `pdf2hwpx` still needs artifact/event implementation for the PDF/DOCX routes.
- Real LibreOffice PDF conversion is not validated yet; local default remains placeholder mode.
- HWPX route stages remain separate and are not implemented by this DOCX-route branch.

## 2026-06-11 pdf2hwpx Worker Placeholder Artifact/Event Validation

Branch: `feat/pdf-docx-pipeline`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 76 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `python3 services/pdf2hwpx-worker/worker.py --generate-local ...` | Passed; generated placeholder HWPX zip. |
| `docker run --rm -v "$PWD/out/pdf2hwpx-worker:/work/out" petoo/file-translation-pdf2hwpx-worker:0.1.0 python /app/service/worker.py --generate-local ...` | Passed; generated placeholder HWPX zip in container. |
| `bash -n scripts/dev/smoke-pdf2hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-pdf2hwpx-live.sh` | Passed. |
| `git diff --check` | Passed. |

Covered by tests:

- `pdf2hwpx-worker` accepts `input_type=pdf` and `input_type=docx`.
- It rejects `input_type=hwpx` and wrong stage names for the PDF/DOCX HWPX placeholder route.
- Input defaults to `{object_prefix}/05_export/marker.docx`.
- Output defaults to `{object_prefix}/06_hwpx/final.hwpx`.
- Optional input and output object key overrides are honored.
- Worker completed output uses `final_hwpx`.
- `stage.failed` events use `PDF2HWPX_WORKER_FAILED`.
- Placeholder HWPX output is a zip containing `mimetype`, `placeholder.json`, and `source/marker.docx`.

Live smoke behavior:

- Started disposable Docker network `ft-pdf2hwpx-live`.
- Started MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`.
- Started RabbitMQ `rabbitmq:3.13-management`.
- Generated a minimal marker DOCX.
- Uploaded it to `file-translation/2026-01-21/12345678/hwpxsmoke1/05_export/marker.docx`.
- Ran `petoo/file-translation-pdf2hwpx-worker:0.1.0 python /app/service/worker.py --consume`.
- Published a command to `q.commands.pdf2hwpx`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/hwpxsmoke1/06_hwpx/final.hwpx` exists in MinIO.
- Verified downloaded placeholder HWPX zip metadata and embedded marker DOCX.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-pdf2hwpx-smoke",
  "outputs": {
    "final_hwpx": "2026-01-21/12345678/hwpxsmoke1/06_hwpx/final.hwpx"
  },
  "stage": "pdf2hwpx"
}
```

Remaining:

- `email_send` still needs artifact/event implementation for the PDF/DOCX route.
- The real custom `pdf2hwpx` library is not integrated yet; local output is a placeholder package.
- Real LibreOffice PDF conversion is not validated yet; local default remains placeholder mode.
- HWPX route stages remain separate and are not implemented by this DOCX-route branch.

## 2026-06-11 Email Provider Contract Validation

Branch: `docs/email-provider-contract`

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 76 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `git diff --check` | Passed. |

Covered by documentation update:

- `email-worker` remains the `email_send` stage worker.
- Mail delivery is provider-based and is not fixed to SMTP.
- Local development defaults to `EMAIL_PROVIDER=mock`.
- Military/internal API delivery is documented as a later `military_api` provider.
- `email-worker` must check `job-service` sendability before provider execution.
- Cancelled, failed, expired, completed, or otherwise non-sendable jobs must not be sent.
- Successful email sends publish `stage.completed`.
- Sendability/provider failures publish `stage.failed`.
- Mock provider should write `{object_prefix}/reports/email_report.json` to MinIO.
- Helm value shape for `email.provider`, `email.sendEnabled`, API base URL, timeout, sender, and `existingSecret` is recorded.

Not run:

- Docker image rebuild/smoke was not needed because this branch changed only Markdown docs.
- Kubernetes/Helm deployment validation was not run because no Helm chart change was made.

## 2026-06-11 Email Worker Provider Implementation Validation

Branch: `feat/email-worker-provider`

| Command | Result |
| --- | --- |
| `docker info --format '{{.ServerVersion}}'` | Passed: Docker server `29.5.3`. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 83 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 8 service smoke commands. |
| `python3 services/email-worker/worker.py --send-local --output out/email-worker-local/email_report.json --job-id local-email-smoke --input-type docx --object-prefix 2026-01-21/12345678/localemail` | Passed; wrote local mock report. |
| `bash -n scripts/dev/smoke-email-worker-live.sh` | Passed. |
| `scripts/dev/build-images.sh` | Passed; all 8 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 8 image smoke commands completed. |
| `scripts/dev/smoke-email-worker-live.sh` | Passed with MinIO `RELEASE.2025-02-07T23-21-09Z`, RabbitMQ `3.13-management`, and a fake `job-service` sendability endpoint. |
| `git diff --check` | Passed. |

Covered by tests:

- `email-worker` accepts the minimal `email_send` command shape with `job_id` and `stage`.
- `email-worker` calls `job-service` sendability before provider execution.
- Non-sendable jobs publish `stage.failed` with `EMAIL_NOT_SENDABLE` and do not call the provider.
- `EMAIL_SEND_ENABLED=false` publishes `stage.failed` with `EMAIL_SEND_DISABLED`.
- Mock provider path writes `reports/email_report.json`.
- Completed event uses `outputs.email_report` and `metrics.provider=mock`.
- `job-service` sendability now returns email-worker details: `input_type`, `user_id`, `object_prefix`, and final artifacts.
- `AppConfig.safe_dict()` exposes only whether email secrets are configured, not the secret values.

Live smoke behavior:

- Started disposable Docker network `ft-email-live`.
- Started MinIO and RabbitMQ.
- Started a fake `job-service` HTTP endpoint for `GET /jobs/live-email-smoke/sendability`.
- Ran `petoo/file-translation-email-worker:0.1.0 python /app/service/worker.py --consume`.
- Published a minimal command to `q.commands.email_send`.
- Received `stage.completed` from `q.events.stage_completed`.
- Verified `2026-01-21/12345678/emailsmoke1/reports/email_report.json` exists in MinIO.
- Verified the report uses provider `mock`, status `sent`, and final DOCX/PDF/HWPX attachment keys.
- Verified the report does not contain token/password-like fields.

Event payload observed:

```json
{
  "event_type": "stage.completed",
  "input_type": "docx",
  "job_id": "live-email-smoke",
  "metrics": {
    "provider": "mock"
  },
  "outputs": {
    "email_report": "2026-01-21/12345678/emailsmoke1/reports/email_report.json"
  },
  "stage": "email_send"
}
```

Remaining:

- `smtp` provider is not implemented and should remain optional.
- `military_api` provider is not implemented until the real closed-network mail API contract is available.
- Helm values/templates still need to wire the documented email settings.
- Full route-level E2E smoke through `job-service` orchestration is still pending.

## 2026-06-11 HWPX Route Skeleton Validation

Branch: `feat/hwpx-rhwp-pipeline`

Implementation commit: `1264b42`

| Command | Result |
| --- | --- |
| `python3 - <<'PY' ... import rhwp ... PY` | `rhwp` unavailable: `ModuleNotFoundError No module named 'rhwp'`. |
| `command -v soffice || true` | No `soffice` binary found in PATH. |
| `command -v libreoffice || true` | No `libreoffice` binary found in PATH. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 94 tests. |
| `scripts/dev/smoke-services.sh` | Passed: all 9 service smoke commands. |
| `scripts/dev/smoke-hwpx-local.sh` | Passed; created sample HWPX, extracted text units, translated with mock provider, replaced HWPX text, and wrote final placeholder HWPX/DOCX/PDF artifacts. |
| `git diff --check` | Passed. |
| `docker version --format '{{.Server.Version}}'` | Passed: Docker server `29.5.3`. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images built with tag `0.1.0`, including `petoo/file-translation-hwpx-worker:0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `docker info --format '{{.Username}}'` | No Docker Hub username reported; image push not attempted. |
| `docker image inspect ...` | Passed; local image IDs recorded in `docs/IMAGE_INVENTORY.md`. |

Covered by tests:

- `hwpx-worker` accepts `input_type=hwpx` for `hwpx_extract` and `hwpx_replace`.
- Wrong input types and wrong stage names are rejected.
- `hwpx_extract` defaults to `{object_prefix}/input/original.hwpx` and writes `{object_prefix}/02_extract/text_units.json`.
- `translate-worker` accepts `hwpx_translate` for `input_type=hwpx`.
- `hwpx_replace` reads original HWPX, `text_units.json`, and `translated_units.json`, then writes `{object_prefix}/04_replace/translated.hwpx`.
- `hwpx_export` reads `{object_prefix}/04_replace/translated.hwpx`, writes placeholder final DOCX/PDF, copies final HWPX to `{object_prefix}/06_hwpx/final.hwpx`, and publishes `stage.completed`.
- `HWPX_RHWP_ENABLED` and `HWPX_H2O_EXPORT_ENABLED` default to `false` and can be overridden through env.

Remaining:

- The current HWPX parser/replacer is a local zip/XML stub, not real `rhwp`.
- LibreOffice H2O/HWPX export is not implemented or validated; `HWPX_H2O_EXPORT_ENABLED=true` fails explicitly.
- Live MinIO/RabbitMQ smoke for the full HWPX route is still pending.
- Helm values/templates do not yet include the new `hwpx-worker` deployment or HWPX config flags.

## 2026-06-11 Current PC Bootstrap Validation

Branch: `test/hwpx-live-minio-rabbitmq-smoke`

Base:

- Created from local `feat/hwpx-rhwp-pipeline`, which tracks `origin/feat/hwpx-rhwp-pipeline`.
- `git log --oneline --decorate --max-count=5` shows `a5381cb` at `HEAD`, `origin/feat/hwpx-rhwp-pipeline`, and local `feat/hwpx-rhwp-pipeline`.

Requested environment checks:

| Command | Result |
| --- | --- |
| `git status` | Passed; on `test/hwpx-live-minio-rabbitmq-smoke`, working tree clean. |
| `git branch --show-current` | Failed; Git `2.17.1` does not support this option. |
| `git rev-parse --abbrev-ref HEAD` | Passed; `test/hwpx-live-minio-rabbitmq-smoke`. |
| `docker version` | Failed; Docker Desktop reports the command cannot be used in this WSL 1 distro. |
| `docker ps` | Failed for the same WSL 1 Docker Desktop reason. |
| `kubectl version --client` | Failed; `kubectl` command not found. |
| `helm version` | Failed; `helm` command not found. |
| `k3d version || true` | `k3d` command not found. |
| `kind version || true` | `kind` command not found. |
| `k3s --version || true` | `k3s` command not found. |
| `scripts/dev/check-env.sh` | Failed with 4 failures: Docker server not reachable, `kubectl` missing, Helm missing, k3d missing. |
| `uname -a` | Reports WSL 1 style kernel `4.4.0-26100-Microsoft`. |
| `wsl.exe -l -v` | `Ubuntu-18.04` is running as WSL `VERSION 1`; Docker Desktop distros are WSL `VERSION 2`. |
| `lsb_release -a` | Ubuntu `18.04.6 LTS` (`bionic`). |
| `command -v docker` | `/mnt/c/Program Files/Docker/Docker/resources/bin/docker`. |
| `command -v kubectl` | Not found. |
| `command -v helm` | Not found. |
| `command -v k3d` | Not found. |
| `ls -la "$HOME/.local/bin"` | Directory exists but does not contain Helm or k3d. |

Python validation:

| Command | Result |
| --- | --- |
| `python3 --version` | Python `3.6.9`. |
| `python3 -m compileall -q services tests` | Failed because Python 3.6 does not support `from __future__ import annotations`. |
| `python3 -m unittest discover -s tests` | Failed with 18 import errors for the same Python 3.6 incompatibility. |
| `python3.10 --version` | Python `3.10.2`. |
| `python3.10 -m compileall -q services tests` | Passed. |
| `python3.10 -m unittest discover -s tests` | Passed: 94 tests. |
| `PYTHON_BIN=python3.10 scripts/dev/smoke-services.sh` | Passed for all 9 services. |
| `PYTHON_BIN=python3.10 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `git diff --check` | Passed before documentation edits. |

Blocked validation:

- Existing local k3d/k8s cluster reuse could not be checked because Docker, kubectl, and k3d are unavailable from this distro.
- CoreDNS, namespace, MinIO, RabbitMQ, PostgreSQL, image build, image smoke, and live MinIO/RabbitMQ smoke validation were not run.
- HWPX live MinIO/RabbitMQ smoke implementation was intentionally not started.

Repeatable recovery sequence:

```powershell
wsl --shutdown
wsl --set-version Ubuntu-18.04 2
wsl -l -v
```

Enable Docker Desktop WSL integration for `Ubuntu-18.04`, reopen WSL, then run:

```bash
docker version
docker ps

curl -fsSL -o /tmp/get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 /tmp/get_helm.sh
HELM_INSTALL_DIR="$HOME/.local/bin" /tmp/get_helm.sh --no-sudo

curl -fsSL -o /tmp/install_k3d.sh https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh
K3D_INSTALL_DIR="$HOME/.local/bin" bash /tmp/install_k3d.sh --no-sudo

export PATH="$HOME/.local/bin:$PATH"
helm version
k3d version
```

Install or restore `kubectl`, then continue:

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

## 2026-06-11 Ubuntu 24.04 WSL2 Recovery Attempt

Branch: `test/hwpx-live-minio-rabbitmq-smoke`

Windows/WSL status:

| Command | Result |
| --- | --- |
| `powershell.exe -NoProfile -Command "wsl -l -v"` | Failed because PowerShell in this environment does not find bare `wsl`. |
| `powershell.exe -NoProfile -Command "wsl --status"` | Failed for the same PowerShell PATH reason. |
| `/mnt/c/Windows/System32/wsl.exe -l -v` | Passed; `Ubuntu-18.04` is default/running on WSL `VERSION 1`; `docker-desktop` and `docker-desktop-data` are running on WSL `VERSION 2`. |
| `/mnt/c/Windows/System32/wsl.exe --status` | Passed; default distribution `Ubuntu-18.04`, default WSL version `2`. |
| `/mnt/c/Windows/System32/wsl.exe --list --online` | Passed; online list includes generic `Ubuntu` but not `Ubuntu-24.04`. |

WSL-internal status:

| Command | Result |
| --- | --- |
| `cat /etc/os-release` | Ubuntu `18.04.6 LTS`. |
| `uname -a` | WSL1-style kernel `4.4.0-26100-Microsoft`. |
| `python3 --version` | Python `3.6.9`. |
| `docker version || true` | Docker Desktop WSL1 distro warning. |
| `docker ps || true` | Same Docker Desktop WSL1 distro warning. |
| `kubectl version --client || true` | `kubectl` not found. |
| `helm version || true` | `helm` not found. |
| `k3d version || true` | `k3d` not found. |

Ubuntu 24.04 install attempts:

| Command | Result |
| --- | --- |
| `/mnt/c/Windows/System32/wsl.exe --install Ubuntu-24.04 --no-launch --web-download` | Failed with invalid distribution name and `WSL_E_DISTRO_NOT_FOUND`. |
| `/mnt/c/Windows/System32/wsl.exe --install Ubuntu --no-launch --web-download` | Ran for over two minutes with no output; no new distro appeared in `wsl -l -v`; process was terminated. |

Conclusion:

- Automated recovery cannot proceed from this WSL1 session.
- No code, Helm, or HWPX smoke implementation was attempted.
- Manual Windows-side Ubuntu 24.04 WSL2 installation/enablement is required.

Manual continuation checklist:

```text
1. Install or enable Ubuntu 24.04 as a WSL2 distro from Windows.
2. Enable Docker Desktop WSL Integration for that distro.
3. Open the repo from Ubuntu 24.04 WSL2.
4. Verify docker ps before installing project tools.
5. Install kubectl, Helm, and k3d if missing.
6. Run the full validation list from the user request.
```

## 2026-06-11 Ubuntu 24.04 WSL2 Follow-up Validation

Branch: `test/hwpx-live-minio-rabbitmq-smoke`

Execution note:

- The Codex shell still runs in Ubuntu 18.04 WSL1, so Ubuntu 24.04 commands were executed with `/mnt/c/Windows/System32/wsl.exe -d Ubuntu-24.04 --cd /mnt/d/Workspaces/Codex/file-translation -- bash -lc '...'`.

Git and OS checks:

| Command | Result |
| --- | --- |
| `git status` | Passed; clean worktree on `test/hwpx-live-minio-rabbitmq-smoke`. |
| `git branch --show-current` | Failed in the current Ubuntu 18.04 shell because Git is still `2.17.1`; `git rev-parse --abbrev-ref HEAD` confirms the branch. |
| `git log --oneline -5` | Shows `3593936`, `c4ad6d8`, `a5381cb`, `1264b42`, `81383f3`. |
| `git fetch --all --prune` | Passed. |
| `git pull --ff-only` | Failed because the local branch has no tracking branch; no remote `origin/test/hwpx-live-minio-rabbitmq-smoke` was listed. |
| `/mnt/c/Windows/System32/wsl.exe -l -v` | `Ubuntu-24.04` is default/running on WSL version 2; `Ubuntu-18.04` remains running on WSL version 1. |
| `cat /etc/os-release` in Ubuntu 24.04 | `Ubuntu 24.04.4 LTS`. |
| `uname -a` in Ubuntu 24.04 | WSL2 kernel `6.18.33.1-microsoft-standard-WSL2`. |
| `python3 --version` in Ubuntu 24.04 | Python `3.12.3`. |
| `ssh -T git@github.com || true` | Authenticates as `Petooooo`. |

Tool checks:

| Command | Result |
| --- | --- |
| `docker version` | Initially failed because the daemon was not running; passed once after starting Docker Desktop; later failed because the Docker Desktop Linux CLI segfaulted. |
| `docker ps` | Passed once after starting Docker Desktop; later Docker socket `_ping` failed. |
| `kubectl version --client || true` | `kubectl` exists as a Docker Desktop CLI-tools symlink but returned `Input/output error` while Docker Desktop integration was unhealthy. |
| `helm version || true` | Initially missing; installed Helm `v3.21.0` into `/home/peto/.local/bin`. |
| `k3d version || true` | Initially missing; installed k3d `v5.9.0` into `/home/peto/.local/bin`. |
| `sudo -n true` | Failed: `sudo: a password is required`; no sudo-based package install was attempted. |

Docker details:

- `/usr/bin/docker` is a symlink to `/mnt/wsl/docker-desktop/cli-tools/usr/bin/docker`.
- The Docker Desktop CLI binary started returning segmentation faults.
- `curl --unix-socket /var/run/docker.sock http://localhost/_ping` fails with `Couldn't connect to server`.
- `curl --unix-socket /mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.sock http://localhost/_ping` also fails.
- Docker Desktop process exists on Windows, but the WSL backend/socket is not usable from Ubuntu 24.04 at the stop point.

Blocked validation:

- `scripts/dev/check-env.sh`, image build/smoke, k3d cluster bootstrap, MinIO/RabbitMQ/PostgreSQL checks, and HWPX live smoke were not run because `docker ps` is not stable.

Manual recovery required:

```text
Docker Desktop -> Settings -> Resources -> WSL Integration -> enable Ubuntu-24.04 -> Apply & Restart
```

Then rerun:

```bash
docker version
docker ps
kubectl version --client
helm version
k3d version
scripts/dev/check-env.sh
```

## 2026-06-12 Ubuntu 24.04 WSL2 Environment Recovery Validation

Branch: `test/hwpx-live-minio-rabbitmq-smoke`

Git and OS checks:

| Command | Result |
| --- | --- |
| `git status` | Passed; clean worktree before adding `scripts/dev/smoke-hwpx-live.sh`. |
| `git branch --show-current` | `test/hwpx-live-minio-rabbitmq-smoke`. |
| `git log --oneline -5` | Shows `36e64a4`, `3593936`, `c4ad6d8`, `a5381cb`, `1264b42`. |
| `git fetch --all --prune` | Passed. |
| `git pull --ff-only` | Failed with no tracking information for the local branch; no `origin/test/hwpx-live-minio-rabbitmq-smoke` branch was pulled. |
| `cat /etc/os-release` | `Ubuntu 24.04.4 LTS`. |
| `uname -a` | WSL2 kernel `6.18.33.1-microsoft-standard-WSL2`. |
| `python3 --version` | Python `3.12.3`. |
| `ssh -T git@github.com || true` | Authenticates as `Petooooo`. |

Tool checks:

| Command | Result |
| --- | --- |
| `docker version` | Passed; Docker Desktop client/server `24.0.6`. |
| `docker ps` | Passed. |
| `curl --unix-socket /var/run/docker.sock http://localhost/_ping || true` | `OK`. |
| `kubectl version --client || true` | Client `v1.28.2`, Kustomize `v5.0.4`. |
| `helm version || true` | Passed with Helm `v3.21.0` from `/home/peto/.local/bin`. |
| `k3d version || true` | Passed with k3d `v5.9.0`. |

Host and image validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 94 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` before cluster bootstrap | Passed with warnings that kind/native k3s are optional and Kubernetes API was not reachable yet. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images built with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/check-env.sh` after cluster bootstrap | Passed with current context `k3d-file-translation-dev`; warnings only for optional kind/native k3s. |

k3d cluster validation:

| Command | Result |
| --- | --- |
| `k3d cluster list` before bootstrap | No clusters existed. |
| `scripts/dev/bootstrap-cluster.sh` | Passed; created k3d cluster `file-translation-dev`, waited for nodes, rolled out CoreDNS, and created namespace `file-translation`. |
| `scripts/dev/smoke-test.sh` | Passed; Kubernetes API reachable, nodes Ready, namespace exists, CoreDNS exists, busybox DNS lookup succeeded. |
| `kubectl config current-context` | `k3d-file-translation-dev`. |
| `kubectl get nodes -o wide` | Server and agent nodes Ready on k3s `v1.32.13+k3s1`. |
| `kubectl get ns file-translation` | Namespace Active. |
| `kubectl -n kube-system get deployment coredns -o wide` | CoreDNS `1/1` available. |

Local dependency validation:

| Command | Result |
| --- | --- |
| `scripts/dev/smoke-pdf2hwpx-live.sh` | Passed; disposable MinIO/RabbitMQ command/event/artifact path works. |
| Disposable `postgres:16-alpine` smoke with `pg_isready` and `select 1` | Passed. |

HWPX live smoke validation:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-hwpx-live.sh` | Passed. |

The new HWPX live smoke verified:

- `input/original.hwpx` was uploaded to MinIO under `2026-01-21/12345678/hwpxlivesmoke1`.
- `hwpx_extract` command was published to `q.commands.hwpx_extract`.
- `hwpx-worker --consume-extract` consumed the command.
- `02_extract/text_units.json` was written to MinIO with `input_type=hwpx` and two text units.
- `stage.completed` for `hwpx_extract` was published to `q.events.stage_completed`.
- `hwpx_translate` command was published to `q.commands.hwpx_translate`.
- `translate-worker --consume-hwpx` consumed the command.
- `03_translate/translated_units.json` was written to MinIO with mock `[ko]` translations.
- At least one `translate.progress` event and one `stage.completed` event for `hwpx_translate` were published.

Remaining validation gaps:

- At this HWPX smoke checkpoint, PostgreSQL was not yet integrated into a project service or Kubernetes local stack; only disposable server accessibility was validated.
- The HWPX live smoke does not yet cover `hwpx_replace`, `hwpx_export`, full job-service orchestration, real `rhwp`, or real LibreOffice H2O.
- Helm chart work remains intentionally untouched.

## 2026-06-12 job-service Orchestration Live Smoke Validation

Branch: `test/job-service-orchestration-live-smoke`

Environment and regression validation:

| Command | Result |
| --- | --- |
| `docker version` | Passed; Docker Desktop client/server `24.0.6`. |
| `docker ps` | Passed; k3d containers are running. |
| `kubectl config current-context` | `k3d-file-translation-dev`. |
| `helm version` | Passed with Helm `v3.21.0`. |
| `k3d version` | Passed with k3d `v5.9.0`. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-test.sh` | Passed; Kubernetes API, nodes, namespace, CoreDNS, and DNS lookup are healthy. |

New live smoke:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-job-orchestration-live.sh` | Passed. |
| `scripts/dev/smoke-job-orchestration-live.sh` | Passed. |

The smoke starts disposable:

- MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`
- RabbitMQ `rabbitmq:3.13-management`
- PostgreSQL `postgres:16-alpine`
- `petoo/file-translation-job-service:0.1.0`

`job-service` configuration:

```text
JOB_SERVICE_REPOSITORY=postgres
JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq
JOB_SERVICE_EVENT_CONSUMER=rabbitmq
```

Verified live orchestration:

- RabbitMQ `q.events.stage_completed` events are consumed by `job-service`.
- PostgreSQL `jobs.payload` JSONB state is inserted and updated by `job-service`.
- `pdf` route: `pdf2docx stage.completed` updates PostgreSQL to `current_stage=docx_extract` and publishes `q.commands.docx_extract`.
- `docx` route: `docx_extract stage.completed` updates PostgreSQL to `current_stage=docx_translate` and publishes `q.commands.docx_translate`.
- `hwpx` route: `hwpx_extract stage.completed` updates PostgreSQL to `current_stage=hwpx_translate` and publishes `q.commands.hwpx_translate`.
- Cancelled `docx` route: `docx_extract stage.completed` updates PostgreSQL to `status=cancelled`, `current_stage=cancelled`, and does not publish `q.commands.docx_translate`.

Smoke output summary:

```json
{"scenarios":[{"completed_stage":"pdf2docx","db_current_stage":"docx_extract","input_type":"pdf","next_queue":"q.commands.docx_extract","next_stage":"docx_extract"},{"completed_stage":"docx_extract","db_current_stage":"docx_translate","input_type":"docx","next_queue":"q.commands.docx_translate","next_stage":"docx_translate"},{"completed_stage":"hwpx_extract","db_current_stage":"hwpx_translate","input_type":"hwpx","next_queue":"q.commands.hwpx_translate","next_stage":"hwpx_translate"},{"cancelled":true,"completed_stage":"docx_extract","db_current_stage":"cancelled","input_type":"docx","next_command_published":false}]}
```

Remaining validation gaps:

- The PostgreSQL repository uses a JSONB aggregate table for live smoke validation, not the future normalized `job_stages` schema.
- Reliable outbox publishing is still not implemented.
- Full worker E2E through every route stage is still pending.
- Helm chart work remains intentionally untouched.

## 2026-06-12 HWPX Replace/Export Live Smoke Validation

Branch: `test/hwpx-replace-export-live-smoke`

Environment and regression validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-job-orchestration-live.sh` | Passed. |

New live smoke:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-hwpx-replace-export-live.sh` | Passed. |
| `scripts/dev/smoke-hwpx-replace-export-live.sh` | Passed. |

The smoke starts disposable:

- MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`
- RabbitMQ `rabbitmq:3.13-management`
- PostgreSQL `postgres:16-alpine`
- `petoo/file-translation-job-service:0.1.0`
- `petoo/file-translation-hwpx-worker:0.1.0` for `hwpx_extract` and `hwpx_replace`
- `petoo/file-translation-translate-worker:0.1.0` for `hwpx_translate`
- `petoo/file-translation-libreoffice-worker:0.1.0` for `hwpx_export`

`job-service` configuration:

```text
JOB_SERVICE_REPOSITORY=postgres
JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq
JOB_SERVICE_EVENT_CONSUMER=rabbitmq
```

Verified live HWPX route:

- The initial HWPX job command includes `input_object_key` for the pre-uploaded MinIO artifact.
- `hwpx_extract` command is consumed by `hwpx-worker` and writes `02_extract/text_units.json`.
- `job-service` consumes `hwpx_extract stage.completed`, updates PostgreSQL, and publishes `q.commands.hwpx_translate`.
- `hwpx_translate` command is consumed by `translate-worker`, writes `03_translate/translated_units.json`, and emits progress plus `stage.completed`.
- `job-service` consumes `hwpx_translate stage.completed`, updates PostgreSQL, and publishes `q.commands.hwpx_replace`.
- `hwpx_replace` command is consumed by `hwpx-worker`, writes `04_replace/translated.hwpx`, and emits `stage.completed`.
- `job-service` consumes `hwpx_replace stage.completed`, updates PostgreSQL, and publishes `q.commands.hwpx_export`.
- `hwpx_export` command is consumed by `libreoffice-worker`, writes placeholder `05_export/final.docx`, placeholder `05_export/final.pdf`, and `06_hwpx/final.hwpx`, then emits `stage.completed`.
- `job-service` consumes `hwpx_export stage.completed`, records `final_docx_key`, `final_pdf_key`, `final_hwpx_key`, and moves the job to `current_stage=email_send`.
- Direct PostgreSQL JSONB validation confirmed `hwpx_extract`, `hwpx_translate`, `hwpx_replace`, and `hwpx_export` are `completed` and the expected artifact keys are persisted.
- A cancelled HWPX job receives a synthetic `hwpx_extract stage.completed` event and remains `status=cancelled`, `current_stage=cancelled`; no `q.commands.hwpx_translate` command is published.

Smoke output summary:

```json
{"artifacts":{"final_docx":"2026-06-12/12345678/hwpxreplaceexport/05_export/final.docx","final_hwpx":"2026-06-12/12345678/hwpxreplaceexport/06_hwpx/final.hwpx","final_pdf":"2026-06-12/12345678/hwpxreplaceexport/05_export/final.pdf","text_units":"2026-06-12/12345678/hwpxreplaceexport/02_extract/text_units.json","translated_hwpx":"2026-06-12/12345678/hwpxreplaceexport/04_replace/translated.hwpx","translated_units":"2026-06-12/12345678/hwpxreplaceexport/03_translate/translated_units.json"},"current_stage":"email_send"}
```

Remaining validation gaps:

- The HWPX worker implementation is still a zip/XML skeleton and not real `rhwp`.
- `hwpx_export` still uses placeholder DOCX/PDF artifacts because `HWPX_H2O_EXPORT_ENABLED=false`.
- The smoke validates sendability at `email_send`; it does not run the email worker or mark the job as fully completed.
- Helm chart work remains intentionally untouched.

## 2026-06-12 email_send End-State Live Smoke Validation

Branch: `test/hwpx-replace-export-live-smoke`

Environment and regression validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-email-worker-live.sh` | Passed. |
| `scripts/dev/smoke-hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-job-orchestration-live.sh` | Passed. |
| `scripts/dev/smoke-hwpx-replace-export-live.sh` | Passed. |

New live smoke:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-email-end-state-live.sh` | Passed. |
| `scripts/dev/smoke-email-end-state-live.sh` | Passed. |

The smoke starts disposable:

- MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`
- RabbitMQ `rabbitmq:3.13-management`
- PostgreSQL `postgres:16-alpine`
- `petoo/file-translation-job-service:0.1.0`
- `petoo/file-translation-email-worker:0.1.0`

`job-service` configuration:

```text
JOB_SERVICE_REPOSITORY=postgres
JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq
JOB_SERVICE_EVENT_CONSUMER=rabbitmq
```

Verified live email end-state:

- `job-service` created an HWPX job and received synthetic upstream `hwpx_extract`, `hwpx_translate`, `hwpx_replace`, and `hwpx_export` `stage.completed` events.
- `job-service` persisted final HWPX/DOCX/PDF keys, moved the job to `current_stage=email_send`, and published `q.commands.email_send`.
- `email-worker` consumed the minimal `email_send` command, called `GET /jobs/{job_id}/sendability`, used the returned artifact keys as attachments, and wrote `reports/email_report.json` to MinIO.
- `email-worker` published `email_send stage.completed` with an `email_report` output.
- `job-service` consumed the email event and marked the job `status=completed`, `current_stage=completed`.
- Direct PostgreSQL JSONB validation confirmed `email_send` is completed and the `email_report` artifact key is persisted.
- A post-completion `GET /jobs/{job_id}/sendability` returns `sendable=false`, which prevents repeat sends for terminal jobs.

Smoke output summary:

```json
{"email_report":"2026-06-12/12345678/emailendstatehwpx/reports/email_report.json","status":"completed"}
```

Notes:

- The upstream HWPX route events are synthetic in this smoke. `scripts/dev/smoke-hwpx-replace-export-live.sh` remains the worker-based live validation for `hwpx_extract -> hwpx_translate -> hwpx_replace -> hwpx_export`.
- The email provider is `mock`; no real SMTP or internal mail API call is made.
- Helm chart work remains intentionally untouched.

## 2026-06-12 HWPX Route-Level E2E Smoke Validation

Branch: `test/hwpx-route-e2e-smoke`

Environment and regression validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-job-orchestration-live.sh` | Passed. |
| `scripts/dev/smoke-hwpx-replace-export-live.sh` | Passed. |
| `scripts/dev/smoke-email-end-state-live.sh` | Passed. |

New route-level smoke:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |

The smoke starts disposable:

- MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`
- RabbitMQ `rabbitmq:3.13-management`
- PostgreSQL `postgres:16-alpine`
- `petoo/file-translation-job-service:0.1.0`
- `petoo/file-translation-hwpx-worker:0.1.0` for `hwpx_extract` and `hwpx_replace`
- `petoo/file-translation-translate-worker:0.1.0` for `hwpx_translate`
- `petoo/file-translation-libreoffice-worker:0.1.0` for `hwpx_export`
- `petoo/file-translation-email-worker:0.1.0` for `email_send`

Verified HWPX route E2E:

- `job-service` create API created an HWPX job with a pre-uploaded MinIO input key and published the initial `hwpx_extract` command.
- The actual workers consumed route commands in order: `hwpx_extract`, `hwpx_translate`, `hwpx_replace`, `hwpx_export`, `email_send`.
- `job-service` consumed each worker `stage.completed` event and published the next command.
- MinIO contains `02_extract/text_units.json`, `03_translate/translated_units.json`, `04_replace/translated.hwpx`, placeholder `05_export/final.docx`, placeholder `05_export/final.pdf`, `06_hwpx/final.hwpx`, and `reports/email_report.json`.
- `email_report.json` uses provider `mock`, status `sent`, and the final HWPX/DOCX/PDF plus translated HWPX attachment keys.
- PostgreSQL JSONB state records `status=completed`, `current_stage=completed`, completed states for all HWPX and email stages, final artifact keys, and the `email_report` artifact.
- RabbitMQ command queues `q.commands.hwpx_extract`, `q.commands.hwpx_translate`, `q.commands.hwpx_replace`, `q.commands.hwpx_export`, and `q.commands.email_send` are empty after completion.
- Mid-route cancellation moves the job to `cancelled` and does not publish `hwpx_translate`.
- Email-stage cancellation makes sendability false and no email report is written.

Smoke output summary:

```json
{"email_report":"2026-06-12/12345678/hwpxroutee2e/reports/email_report.json","status":"completed"}
```

Remaining validation gaps at the time of this HWPX run:

- DOCX route-level E2E smoke was still pending here and is covered in the following DOCX validation section.
- PDF route-level E2E smoke remains after DOCX E2E.
- HWPX `rhwp` and LibreOffice H2O remain placeholder/stub paths.
- Helm chart work remains intentionally untouched.

## 2026-06-12 DOCX Route-Level E2E Smoke Validation

Branch: `test/docx-route-e2e-smoke`

Environment and regression validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-hwpx-live.sh` | Passed. |
| `scripts/dev/smoke-job-orchestration-live.sh` | Passed after PostgreSQL readiness hardening. |
| `scripts/dev/smoke-hwpx-replace-export-live.sh` | Passed after PostgreSQL readiness hardening. |
| `scripts/dev/smoke-email-end-state-live.sh` | Passed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |

New route-level smoke:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |

The smoke starts disposable:

- MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`
- RabbitMQ `rabbitmq:3.13-management`
- PostgreSQL `postgres:16-alpine`
- `petoo/file-translation-job-service:0.1.0`
- `petoo/file-translation-docx-extract-worker:0.1.0` for `docx_extract`
- `petoo/file-translation-translate-worker:0.1.0` for `docx_translate`
- `petoo/file-translation-docx-replace-worker:0.1.0` for `docx_replace`
- `petoo/file-translation-libreoffice-worker:0.1.0` for `docx_export` and `docx_marker`
- `petoo/file-translation-pdf2hwpx-worker:0.1.0` for `pdf2hwpx`
- `petoo/file-translation-email-worker:0.1.0` for `email_send`

Verified DOCX route E2E:

- `job-service` create API created a DOCX job with a pre-uploaded MinIO input key and published the initial `docx_extract` command.
- The actual workers consumed route commands in order: `docx_extract`, `docx_translate`, `docx_replace`, `docx_export`, `docx_marker`, `pdf2hwpx`, `email_send`.
- `job-service` consumed each worker `stage.completed` event and published the next command.
- MinIO contains `02_extract/text_units.json`, `03_translate/translated_units.json`, `04_replace/translated.docx`, `05_export/final.docx`, placeholder `05_export/final.pdf`, `05_export/marker.docx`, placeholder `06_hwpx/final.hwpx`, and `reports/email_report.json`.
- `translated.docx` and `final.docx` contain mock `[ko]` translated DOCX text.
- `marker.docx` contains the marker token used before `pdf2hwpx`.
- Placeholder `final.hwpx` contains `placeholder.json` with `stage=pdf2hwpx`, `input_type=docx`, and the embedded `source/marker.docx`.
- `email_report.json` uses provider `mock`, status `sent`, and the final DOCX/PDF/HWPX attachment keys.
- PostgreSQL JSONB state records `status=completed`, `current_stage=completed`, completed states for all DOCX, `pdf2hwpx`, and email stages, final artifact keys, and the `email_report` artifact.
- RabbitMQ command queues `q.commands.docx_extract`, `q.commands.docx_translate`, `q.commands.docx_replace`, `q.commands.docx_export`, `q.commands.docx_marker`, `q.commands.pdf2hwpx`, and `q.commands.email_send` are empty after completion.
- Mid-route cancellation moves the job to `cancelled` and does not publish `docx_translate`.
- Email-stage cancellation makes sendability false and no email report is written.

Smoke output summary:

```json
{"email_report":"2026-06-12/12345678/docxroutee2e/reports/email_report.json","status":"completed"}
```

Validation note:

- Two initial clean-mode runs of `scripts/dev/smoke-hwpx-replace-export-live.sh` failed at PostgreSQL readiness before worker startup. A preserved-container rerun passed, confirming a readiness timing issue rather than a contract failure. `scripts/dev/smoke-hwpx-replace-export-live.sh` and `scripts/dev/smoke-job-orchestration-live.sh` now use an explicit `postgres_ready` flag like the newer E2E smokes.

Remaining validation gaps at the time of this DOCX run:

- PDF route-level E2E smoke was still pending here and is covered in the following PDF validation section.
- Real LibreOffice PDF export, real `pdf2hwpx`, and real email delivery remain pending.
- Helm chart work remains intentionally untouched.

## 2026-06-12 PDF Route-Level E2E Smoke Validation

Branch: `test/pdf-route-e2e-smoke`

Environment and regression validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf2docx-live.sh` | Passed. |

New route-level smoke:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |

The smoke starts disposable:

- MinIO `minio/minio:RELEASE.2025-02-07T23-21-09Z`
- RabbitMQ `rabbitmq:3.13-management`
- PostgreSQL `postgres:16-alpine`
- `petoo/file-translation-job-service:0.1.0`
- `petoo/file-translation-pdf2docx-worker:0.1.0` for `pdf2docx`
- `petoo/file-translation-docx-extract-worker:0.1.0` for `docx_extract`
- `petoo/file-translation-translate-worker:0.1.0` for `docx_translate`
- `petoo/file-translation-docx-replace-worker:0.1.0` for `docx_replace`
- `petoo/file-translation-libreoffice-worker:0.1.0` for `docx_export` and `docx_marker`
- `petoo/file-translation-pdf2hwpx-worker:0.1.0` for `pdf2hwpx`
- `petoo/file-translation-email-worker:0.1.0` for `email_send`

Verified PDF route E2E:

- `job-service` create API created a PDF job with a pre-uploaded MinIO input key and published the initial `pdf2docx` command.
- The sample PDF was generated with `petoo/pdf2docx:0.5.13-py311-static`.
- `pdf2docx-worker` consumed `q.commands.pdf2docx`, invoked the static anchored converter, and wrote `01_pdf2docx/converted.docx`, `reports/pdf2docx.report.json`, and `reports/pdf2docx.report.md`.
- The actual workers consumed route commands in order: `pdf2docx`, `docx_extract`, `docx_translate`, `docx_replace`, `docx_export`, `docx_marker`, `pdf2hwpx`, `email_send`.
- `job-service` consumed each worker `stage.completed` event and published the next command.
- MinIO contains all route artifacts from converted DOCX through final DOCX/PDF, marker DOCX, placeholder HWPX, and `reports/email_report.json`.
- Converted DOCX contains the static anchored smoke sample text; translated/final DOCX artifacts contain mock `[ko]` translated text.
- Placeholder `final.hwpx` contains `placeholder.json` with `stage=pdf2hwpx`, `input_type=pdf`, and the embedded `source/marker.docx`.
- `email_report.json` uses provider `mock`, status `sent`, and the final DOCX/PDF/HWPX attachment keys.
- PostgreSQL JSONB state records `status=completed`, `current_stage=completed`, completed states for all PDF/DOCX, `pdf2hwpx`, and email stages, final artifact keys, and the `email_report` artifact.
- RabbitMQ command queues `q.commands.pdf2docx`, `q.commands.docx_extract`, `q.commands.docx_translate`, `q.commands.docx_replace`, `q.commands.docx_export`, `q.commands.docx_marker`, `q.commands.pdf2hwpx`, and `q.commands.email_send` are empty after completion.
- Mid-route cancellation moves the job to `cancelled` and does not publish `docx_extract`.
- Email-stage cancellation makes sendability false and no email report is written.

Smoke output summary:

```json
{"email_report":"2026-06-12/12345678/pdfroutee2e/reports/email_report.json","status":"completed"}
```

Remaining validation gaps:

- Helm/local-stack deployment remains pending.
- Real LibreOffice PDF export, real `pdf2hwpx`, real HWPX `rhwp`, and real email delivery remain pending implementation tracks.

## 2026-06-12 Operation/API/Replacement Documentation Validation

Branch: `test/pdf-route-e2e-smoke`

Documentation scope:

- `docs/USAGE.md`
- `docs/API.md`
- `docs/ADMIN_UI.md`
- `docs/INTEGRATION_GUIDE.md`
- `docs/REPLACEMENT_GUIDE.md`
- `docs/CLOSED_NETWORK_DEPLOYMENT.md`
- `docs/CONTRACTS.md`
- `docs/PIPELINE.md`
- `docs/ARCHITECTURE.md`
- `docs/PROJECT_PLAN.md`
- `docs/TROUBLESHOOTING.md`
- `docs/IMAGE_INVENTORY.md`

Regression validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 96 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |
| `git diff --check` | Passed. |

Validated documentation contracts:

- `job-service` is recorded as the only public API entry point for frontend/admin/user clients.
- Frontend/admin/user clients are explicitly prohibited from publishing RabbitMQ messages.
- `POST /jobs`, job status, stages, artifacts, cancel, retry, download, and admin API targets are documented.
- Upload options are documented as job-service mediated multipart upload or job-service-issued presigned upload URL.
- Admin UI requirements are documented without adding an admin frontend implementation.
- `email-worker` replacement is documented through the `MailProvider` interface and `EMAIL_PROVIDER=mock|smtp|military_api`.
- `pdf2hwpx-worker` replacement is documented around the placeholder entrypoint, marker DOCX input, final HWPX output, and `¡` marker restoration policy.
- Closed-network external RabbitMQ variables and required queue names are documented.
- Queue initialization is documented as a future idempotent Helm install/upgrade Job.

Remaining validation gaps:

- Helm/local-stack deployment remains pending.
- The target public upload/download/retry/admin endpoints are documented but not all implemented.
- `EMAIL_PROVIDER=smtp`, `EMAIL_PROVIDER=military_api`, and real custom `pdf2hwpx` remain replacement targets.

## 2026-06-12 job-service API/Admin UI Readiness Validation

Branch: `feat/admin-api-ui-readiness`

New API/UI scope:

- `GET /jobs/{job_id}/stages`
- `GET /jobs/{job_id}/artifacts`
- `POST /jobs/{job_id}/retry`
- `GET /admin/jobs`
- `GET /admin/jobs/{job_id}`
- `GET /admin`

Regression validation:

| Command | Result |
| --- | --- |
| `bash -n scripts/dev/smoke-admin-api.sh` | Passed. |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest tests.test_job_service_api` | Passed: 4 tests. |
| `python3 -m unittest discover -s tests` | Passed: 100 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh` | Passed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |

`scripts/dev/smoke-admin-api.sh` verifies:

- a completed DOCX job can be inspected through `GET /jobs/{job_id}`, stages, artifacts, admin list, and admin detail APIs
- `reports/email_report.json` appears in artifact listings
- a cancelled job is visible through admin status filtering
- a failed job is visible through admin status filtering
- retry of a failed PDF job republishes `q.commands.pdf2docx` through `job-service`
- retry of a completed job returns `409 retry_not_allowed`
- `/admin` serves a lightweight HTML skeleton
- the Admin UI skeleton references job-service APIs and does not expose RabbitMQ access

Remaining validation gaps:

- Helm/local-stack deployment remains pending.
- Admin UI is a lightweight skeleton, not a full production console.
- Retry does not yet enforce MinIO artifact existence or attempt-limit policy.
- Download streaming/presigned download API remains pending.

## 2026-06-12 Reliability/Admin/Usage Replan Audit

Branch: `docs/reliability-admin-usage-replan`

Audit commands:

| Command | Result |
| --- | --- |
| `git fetch --all --prune` | Passed. |
| `git switch feat/admin-api-ui-readiness` | Passed. |
| `git pull --ff-only` | Skipped because the local branch has no upstream. |
| `git switch -c docs/reliability-admin-usage-replan` | Passed. |
| `rg -n "basic_ack|basic_nack|basic_consume|start_consuming|auto_ack|prefetch|basic_qos|consume|process_.*command|sendability|retry|attempt|stage\\.completed|stage\\.failed|progress|heartbeat|lease|idempot" services tests scripts -S` | Passed; identified common RabbitMQ consumer, worker consume paths, job-service retry/sendability, and lack of lease/idempotency fields. |

Current audit findings:

- `services/common/ft_common/rabbitmq.py` acks worker command messages after `handler(...)` returns.
- Worker command handlers perform MinIO download, conversion/export, MinIO upload, and event publish before the ack.
- `services/job-service/job_service/rabbitmq.py` acks event messages after `service.handle_event(...)` returns.
- `services/job-service/job_service/orchestrator.py` no-ops terminal jobs, but duplicate in-route `stage.completed` events can publish a duplicate downstream command.
- `services/job-service/job_service/models.py` has `attempts` and timestamps, but no `lease_until`, `last_heartbeat_at`, `claim_id`, `idempotency_key`, `max_attempts`, or `next_retry_at`.
- `email-worker` calls sendability before sending, but duplicate concurrent `email_send` commands can still call the provider before job-service records `completed`.

Documentation validation added:

- `docs/RELIABILITY_REPLAN.md` records current state, risk assessment, target architecture, code change plan, API/Admin gap, usage/integration gap, and verification plan.

Planning branch validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 100 tests. |
| `git diff --check` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh` | Passed. |

Validation still required after implementation:

```bash
python3 -m compileall -q services tests
python3 -m unittest discover -s tests
PYTHON_BIN=python3 scripts/dev/smoke-services.sh
PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh
scripts/dev/check-env.sh
scripts/dev/build-images.sh
scripts/dev/smoke-images.sh
PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh
scripts/dev/smoke-hwpx-route-e2e.sh
scripts/dev/smoke-docx-route-e2e.sh
scripts/dev/smoke-pdf-route-e2e.sh
scripts/dev/smoke-long-running-stage-safety.sh
scripts/dev/smoke-usage-flow.sh
```

## 2026-06-12 Long-Running Stage Safety MVP Validation

Branch: `feat/long-running-stage-safety`

Implementation validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 105 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-long-running-stage-safety.sh` | Passed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |

`scripts/dev/smoke-long-running-stage-safety.sh` verifies:

- first stage claim returns `CLAIMED`
- duplicate running stage command returns `ALREADY_RUNNING`
- heartbeat updates the claimed stage
- duplicate `stage.completed` event does not publish another downstream command
- completed stage command returns `ALREADY_COMPLETED`
- cancelled job claim returns `JOB_CANCELLED`
- attempt above `max_attempts` returns `MAX_ATTEMPTS_EXCEEDED` and fails the job
- duplicate running `email_send` command returns `ALREADY_RUNNING`
- completed `email_send` command returns `ALREADY_COMPLETED`

Route-level validation notes:

- HWPX, DOCX, and PDF route E2E smokes passed after rebuilding images with the new worker runtime.
- Route-level workers now consume job-service-created commands with `command_id`, claim via `job-service`, ack after claim/no-op, and complete through the existing worker event -> job-service next-command path.
- Workers still do not publish next-stage commands.
- Frontend/admin/user clients still do not publish RabbitMQ messages.

Remaining validation gaps:

- Direct stage live smokes that publish synthetic RabbitMQ commands without `command_id` remain legacy compatibility tests and do not exercise ack-after-claim.
- Automatic delayed retry/backoff behavior is not implemented or validated on that branch; stale lease recovery is validated separately below.
- Provider-level idempotency for real `military_api` email delivery is not implemented or validated.
- Helm/local-stack remains pending and was not run.

## 2026-06-12 Stale Lease Reconciler MVP Validation

Branch: `feat/stale-lease-reconciler`

Implementation validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 110 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-long-running-stage-safety.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-stale-lease-reconciler.sh` | Passed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |
| `git diff --check` | Passed. |

`scripts/dev/smoke-stale-lease-reconciler.sh` verifies:

- expired running `pdf2docx` lease is reconciled by `POST /internal/reconcile/stale-leases`
- `job-service` republishes a retry command for the same stage when attempts remain
- retry command increments the stage attempt from `1` to `2`
- late `stage.completed` from previous attempt does not publish a downstream command
- expired running stage at `max_attempts=3` fails terminally
- cancelled/cancel-requested stale job does not retry and moves to cancelled terminal state
- stale `email_send` fails without auto-retry to avoid duplicate sends

Stage/admin visibility validated through job JSON:

- `lease_expired`
- `reconciled_at`
- `retry_count`
- `retry_backoff_seconds`
- `next_retry_at`
- `last_reconcile_reason`
- `stale_attempts`

Remaining validation gaps:

- Full verification suite and route E2E rerun are required before merging beyond this branch.
- Retry is immediate; delayed retry/backoff, RabbitMQ DLQ policy, and Helm CronJob wiring are not implemented or validated.
- Provider-level idempotency for real `military_api` email delivery is not implemented or validated.

## 2026-06-13 Monitoring Readiness / Uptime Kuma Readiness Validation

Branch: `feat/monitoring-readiness`

Implementation validation:

| Command | Result |
| --- | --- |
| `python3 -m compileall -q services tests` | Passed. |
| `python3 -m unittest discover -s tests` | Passed: 113 tests. |
| `PYTHON_BIN=python3 scripts/dev/smoke-services.sh` | Passed for all 9 service smoke commands. |
| `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh` | Passed. |
| `scripts/dev/check-env.sh` | Passed with optional warnings for missing kind/native k3s. |
| `scripts/dev/build-images.sh` | Passed; all 9 service images rebuilt with tag `0.1.0`. |
| `scripts/dev/smoke-images.sh` | Passed; all 9 image smoke commands completed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-long-running-stage-safety.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-stale-lease-reconciler.sh` | Passed. |
| `PYTHON_BIN=python3 scripts/dev/smoke-monitoring-readiness.sh` | Passed. |
| `scripts/dev/smoke-hwpx-route-e2e.sh` | Passed after `/readyz` was corrected to dependency-only readiness. |
| `scripts/dev/smoke-docx-route-e2e.sh` | Passed. |
| `scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |
| `bash -n scripts/dev/smoke-monitoring-readiness.sh scripts/dev/smoke-hwpx-route-e2e.sh scripts/dev/smoke-docx-route-e2e.sh scripts/dev/smoke-pdf-route-e2e.sh` | Passed. |
| `git diff --check` | Passed before final commit. |

`scripts/dev/smoke-monitoring-readiness.sh` verifies:

- `/healthz` returns HTTP 200 and `status=ok`
- `/readyz` returns HTTP 200 and `overall_status=healthy` when required dependencies are available or skipped by configuration
- `/admin/health` returns `overall_status`
- `/admin/workers` returns stage-activity-derived worker/stage summary
- `/admin/queues` returns configured queue names with `status=skipped` when RabbitMQ is disabled
- expired running lease appears in `/admin/health` as `overall_status=degraded` and `stale_running_count=1`
- `POST /internal/reconcile/stale-leases` clears the stale running count when attempts remain
- max-attempt stale failure appears in `failed_job_count` and `recent_failed_jobs`
- `/admin` loads and references monitoring APIs without exposing RabbitMQ queue names or secrets in the HTML
- intentionally unavailable RabbitMQ/MinIO dependencies make `/readyz`, `/admin/health`, and `/admin/queues` report unhealthy while `/healthz` remains process-alive OK

Route E2E validation notes:

- The first HWPX route E2E rerun exposed a bad readiness boundary: `/readyz` originally depended on queue existence checks and returned HTTP 503 before all command queues were declared.
- Fixed readiness so `/readyz` checks required dependency connectivity only.
- Queue existence/depth remains visible through `/admin/queues` and `/admin/health`.
- HWPX, DOCX, and PDF route E2E smokes passed after rebuilding images with the corrected job-service.

Remaining validation gaps:

- Dedicated worker heartbeat is not implemented; `/admin/workers` remains stage-activity-derived.
- AMQP passive declare does not expose unacked counts; optional RabbitMQ Management API metrics remain future work.
- Uptime Kuma server installation and monitor auto-registration were not implemented or validated.
- Helm/local-stack Service/Ingress exposure and auth policy remain pending.
