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

- Pipeline replan committed as `c71aca7` with message `docs: replan multi-input pipeline contracts`.

Next recommended step:

- Start `feat/job-service-input-routing` from this replan commit after it is committed.

## 2026-06-10 15:02 KST - Job-service input routing

Done:

- Created/used branch `feat/job-service-input-routing` from checkpoint `716f361`.
- Implemented `job-service` route ownership for `pdf`, `docx`, and `hwpx` input types.
- Added input validation and initial stage mapping: `pdf -> pdf2docx`, `docx -> docx_extract`, `hwpx -> hwpx_extract`.
- Added in-memory job metadata, stage state, artifact/progress fields, and route persistence matching the revised metadata contract.
- Added command publisher interface plus in-memory publisher for queue/message verification.
- Added worker event handling skeleton for `stage.completed`, `stage.failed`, and progress events.
- Enforced cancel behavior so `cancel_requested` jobs do not publish the next stage.
- Added a small stdlib HTTP API for create/query/cancel/sendability/event intake.
- Added focused unit tests for routing, invalid input rejection, cancel blocking, event-driven next-stage selection, progress/artifact query payloads, and final `email_send -> completed` flow.
- No worker conversion, rhwp, LibreOffice, pdf2hwpx, Helm, or E2E implementation was added on this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 21 tests.
- `scripts/dev/smoke-services.sh` passes.
- `git diff --check` passes.

Commit:

- Job-service routing implementation committed as `3934cf3` with message `feat: add job-service input routing`.

Next recommended step:

- Continue with RabbitMQ-backed publisher/consumer integration or start `feat/pdf2docx-static-worker` after validating the custom `petoo/pdf2docx:0.5.13-py311-static` image in an environment with Docker access.

## 2026-06-10 15:38 KST - RabbitMQ orchestration adapters

Done:

- Created branch `feat/rabbitmq-orchestration` from `feat/job-service-input-routing`.
- Added `JOB_SERVICE_COMMAND_PUBLISHER` with `memory` default and `rabbitmq` opt-in.
- Added `JOB_SERVICE_EVENT_CONSUMER` with `disabled` default and `rabbitmq` opt-in.
- Added RabbitMQ command publisher adapter for durable queue declaration and persistent JSON command publish.
- Added RabbitMQ event consumer adapter for event queue declaration, JSON decode, `job-service` event dispatch, ack, and non-requeue nack on bad events.
- Kept the in-memory publisher as the default so host-side tests and service smoke commands do not require RabbitMQ.
- Added `pika==1.3.2` to the `job-service` container runtime requirements.
- Added unit tests for publisher mode selection, RabbitMQ queue mapping, command publish payloads, event decode, ack/nack behavior, and consumer queue registration.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 28 tests.
- `scripts/dev/smoke-services.sh` passes.
- `git diff --check` passes.

Commit:

- RabbitMQ adapter implementation committed as `1d3caed` with message `feat: add RabbitMQ orchestration adapters`.

Next recommended step:

- Rebuild/smoke the `job-service` image when Docker is available, then either wire PostgreSQL persistence/outbox or proceed to `feat/pdf2docx-static-worker` after validating `petoo/pdf2docx:0.5.13-py311-static`.

## 2026-06-10 15:56 KST - Local environment and image validation resumed

Done:

- Re-ran local environment validation after Docker/kubectl access was restored.
- Confirmed existing k3d cluster `file-translation-dev` is reachable; no cluster recreation was needed.
- Re-ran Kubernetes namespace/CoreDNS smoke validation.
- Rebuilt all `petoo/file-translation-*` local service images with tag `0.1.0`.
- Smoke-tested all service images after the `job-service` `pika==1.3.2` runtime dependency was added.
- Pulled and validated `petoo/pdf2docx:0.5.13-py311-static`.
- Ran the static anchored pdf2docx container smoke test with report output.
- Added `out/` to `.gitignore` because the pdf2docx smoke test writes local validation artifacts there.
- Updated `docs/IMAGE_INVENTORY.md` with current local image IDs and the custom pdf2docx registry digest.

Verified:

- `scripts/dev/check-env.sh` passes with Docker server, kubectl, Helm, k3d, and Kubernetes API reachable.
- `scripts/dev/smoke-test.sh` passes; nodes Ready, namespace exists, CoreDNS exists, DNS lookup succeeds.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- `docker pull petoo/pdf2docx:0.5.13-py311-static` passes with digest `sha256:d3ef804baceed3516e8ce89df3a33abfde00c1fd348541c3b8ad0cb9fc404f0f`.
- `python -m pdf2docx.static_anchored.cli --help` works inside the custom image.
- Static anchored smoke generated `sample.pdf`, `sample.static.docx`, `sample.static.report.json`, and `sample.static.report.md`.

Commit:

- Environment/image validation documentation committed as `ca38e01` with message `docs: record restored environment validation`.

Next recommended step:

- Start `feat/pdf2docx-static-worker` from the current validated checkpoint, or continue with PostgreSQL persistence/outbox if job state durability should come first.

## 2026-06-10 16:14 KST - pdf2docx static worker runtime

Done:

- Created branch `feat/pdf2docx-static-worker` from `feat/rabbitmq-orchestration`.
- Changed `pdf2docx-worker` Dockerfile to use `petoo/pdf2docx:0.5.13-py311-static` as its base image.
- Added `PDF2DOCX_IMAGE` and `PDF2DOCX_ENABLE_REPORTS` config support.
- Added a `pdf2docx_worker` runtime package with a testable wrapper around `python -m pdf2docx.static_anchored.cli`.
- Added `--convert-local` worker mode for local/container validation without RabbitMQ or MinIO.
- Added optional JSON/Markdown report handling for the static anchored converter.
- Added unit tests for command construction, report paths, PDF input validation, fake conversion output mapping, and config parsing.
- Did not implement RabbitMQ command consumption, MinIO artifact transfer, or downstream stage enqueueing in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 34 tests.
- `scripts/dev/smoke-services.sh` passes.
- `git diff --check` passes.
- `scripts/dev/build-images.sh` passes; `pdf2docx-worker` builds from `petoo/pdf2docx:0.5.13-py311-static`.
- `scripts/dev/smoke-images.sh` passes.
- `docker run --rm petoo/file-translation-pdf2docx-worker:0.1.0 python -m pdf2docx.static_anchored.cli --help` passes.
- `pdf2docx-worker --convert-local` converted `out/pdf2docx-worker/sample.pdf` into `worker.static.docx` plus JSON/Markdown reports.

Commit:

- pdf2docx worker implementation committed as `957830c` with message `feat: wire pdf2docx worker to static anchored converter`.

Next recommended step:

- Add worker-side RabbitMQ command consumption and MinIO download/upload helpers, then have `pdf2docx-worker` publish only `stage.completed`/`stage.failed` events.

## 2026-06-10 16:38 KST - pdf2docx worker artifact/event flow

Done:

- Created branch `feat/pdf2docx-worker-artifacts` from `feat/pdf2docx-static-worker`.
- Added common `ft_common.minio_store` helper for MinIO download/upload.
- Added common `ft_common.rabbitmq` JSON publisher/consumer helper for worker command/event plumbing.
- Added `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` to runtime config with secret-safe `safe_dict()` output.
- Added `pdf2docx-worker` artifact key calculation from `{object_prefix}` using the required MinIO convention.
- Added `pdf2docx-worker --consume` mode to consume `q.commands.pdf2docx`, download the input PDF, run static anchored conversion, upload DOCX/report artifacts, and publish `stage.completed` or `stage.failed`.
- Ensured `pdf2docx-worker` still does not enqueue any next-stage command.
- Added `minio==7.2.20` and `pika==1.3.2` to the `pdf2docx-worker` image runtime.
- Added brokerless/minio-less tests using fake stores and fake RabbitMQ connections.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 45 tests.
- `scripts/dev/smoke-services.sh` passes.
- `git diff --check` passes.
- `scripts/dev/build-images.sh` passes; `pdf2docx-worker` installs `minio==7.2.20` and `pika==1.3.2`.
- `scripts/dev/smoke-images.sh` passes.
- `pdf2docx-worker --convert-local` still converts the sample PDF and writes DOCX plus JSON/Markdown reports.
- Container dependency check confirms `minio 7.2.20` and `pika 1.3.2`.

Commit:

- pdf2docx artifact/event implementation committed as `e539dc1` with message `feat: add pdf2docx worker artifact event flow`.

Next recommended step:

- Deploy or configure local MinIO/RabbitMQ services, seed a sample PDF object, and run a live `pdf2docx-worker --consume` smoke test through the real command/event queues.

## 2026-06-10 17:23 KST - pdf2docx live MinIO/RabbitMQ smoke

Done:

- Created branch `test/pdf2docx-worker-live-smoke` from `feat/pdf2docx-worker-artifacts`.
- Added `scripts/dev/smoke-pdf2docx-live.sh`.
- The script starts disposable Docker MinIO and RabbitMQ containers, generates a sample PDF with `petoo/pdf2docx:0.5.13-py311-static`, seeds the input object, starts `pdf2docx-worker --consume`, publishes a `pdf2docx` command, waits for the worker event, and verifies the converted DOCX/report objects in MinIO.
- Kept the worker orchestration rule intact: the worker publishes `stage.completed` or `stage.failed` only and does not enqueue downstream stages.
- Found and fixed a Docker smoke issue where the script used service names `minio` and `rabbitmq` without network aliases.

Verified:

- `bash -n scripts/dev/smoke-pdf2docx-live.sh` passes.
- `scripts/dev/smoke-pdf2docx-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The smoke event contained `event_type=stage.completed`, `stage=pdf2docx`, and output keys under `2026-01-21/12345678/a8f3k2p9/...`.
- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 45 tests.
- `scripts/dev/smoke-services.sh` passes.
- `git diff --check` passes.

Commit:

- Live smoke script committed as `e8fa11d` with message `test: add pdf2docx live smoke script`.

Next recommended step:

- Start `feat/pdf-docx-pipeline` to implement the next DOCX-side artifact/event stage, beginning with `docx_extract` and its `text_units.json` contract.

## 2026-06-10 17:54 KST - docx_extract artifact/event flow

Done:

- Created branch `feat/pdf-docx-pipeline` from `test/pdf2docx-worker-live-smoke`.
- Implemented `docx-extract-worker` runtime package.
- Added standard-library DOCX extraction from `word/document.xml` into `text_units.json`.
- Added `docx-extract-worker --extract-local` for host/container validation.
- Added `docx-extract-worker --consume` to consume `q.commands.docx_extract`, download DOCX input from MinIO, upload `02_extract/text_units.json`, and publish `stage.completed` or `stage.failed`.
- Supported both `input_type=docx` and `input_type=pdf` for `docx_extract`; PDF route defaults to `01_pdf2docx/converted.docx`, DOCX route defaults to `input/original.docx`.
- Added `scripts/dev/smoke-docx-extract-live.sh` for disposable Docker MinIO/RabbitMQ live validation.
- Added `source_lang` and `target_lang` to job-service command envelopes so downstream `text_units.json` can preserve language metadata.
- Did not implement translation, DOCX replacement, LibreOffice export, marker DOCX generation, pdf2hwpx, or Helm changes in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 51 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- Host `docx-extract-worker --extract-local` produced two text units from a sample DOCX.
- Container `docx-extract-worker --extract-local` produced two text units from the same sample DOCX.
- `scripts/dev/smoke-docx-extract-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The live smoke event contained `event_type=stage.completed`, `stage=docx_extract`, and output key `2026-01-21/12345678/docxsmoke1/02_extract/text_units.json`.
- `git diff --check` passes.

Commit:

- Implementation committed as `10372ae` with message `feat: add docx extract artifact flow`.

Next recommended step:

- Continue `feat/pdf-docx-pipeline` with `docx_translate`: implement mock translation provider artifact/event flow from `text_units.json` to `translated_units.json`.

## 2026-06-10 18:28 KST - docx_translate artifact/event flow

Done:

- Continued branch `feat/pdf-docx-pipeline`.
- Implemented `translate-worker` runtime package.
- Added translation provider abstraction with local `mock` provider default and HTTP provider skeleton for the internal `string` + `uid` API shape.
- Added `translate-worker --translate-local` for host/container validation.
- Added `translate-worker --consume` to consume `q.commands.docx_translate`, download `02_extract/text_units.json`, upload `03_translate/translated_units.json`, publish `translate.progress`, and publish `stage.completed` or `stage.failed`.
- Supported both `input_type=docx` and `input_type=pdf` for the DOCX translation route.
- Added `scripts/dev/smoke-docx-translate-live.sh` for disposable Docker MinIO/RabbitMQ live validation.
- Did not implement DOCX replacement, LibreOffice export, marker DOCX generation, pdf2hwpx, HWPX translation, PostgreSQL persistence, or Helm changes in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 56 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- Host `translate-worker --translate-local` produced mock translated units from a sample `text_units.json`.
- Container `translate-worker --translate-local` produced the same mock translated units.
- `scripts/dev/smoke-docx-translate-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The live smoke observed at least one `translate.progress` event and a `stage.completed` event with output key `2026-01-21/12345678/translatesmoke1/03_translate/translated_units.json`.
- `git diff --check` passes.

Commit:

- Implementation committed as `e0f06ee` with message `feat: add docx translate artifact flow`.

Next recommended step:

- Continue `feat/pdf-docx-pipeline` with `docx_replace`: read DOCX plus `translated_units.json`, write `04_replace/translated.docx`, and publish only worker stage events.
