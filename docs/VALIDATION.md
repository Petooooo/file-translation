# Validation

Last updated: 2026-06-10 23:00 KST

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
