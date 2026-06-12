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

## 2026-06-10 23:00 KST - docx_replace artifact/event flow

Done:

- Continued branch `feat/pdf-docx-pipeline`.
- Implemented `docx-replace-worker` runtime package.
- Added `docx-replace-worker --replace-local` for host/container validation.
- Added `docx-replace-worker --consume` to consume `q.commands.docx_replace`, download the route-specific DOCX input plus `02_extract/text_units.json` and `03_translate/translated_units.json`, upload `04_replace/translated.docx`, and publish `stage.completed` or `stage.failed`.
- Supported both `input_type=pdf` and `input_type=docx` for the DOCX replacement route.
- Added `scripts/dev/smoke-docx-replace-live.sh` for disposable Docker MinIO/RabbitMQ live validation.
- Documented the current replacement MVP limitation: only `word/document.xml` `w:t` nodes are replaced using `paragraph_index`, `run_index`, and `text_index`.
- Did not implement LibreOffice export, marker DOCX generation, pdf2hwpx, HWPX replacement, PostgreSQL persistence, or Helm changes in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 61 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- Host `docx-replace-worker --replace-local` replaced two sample DOCX text nodes.
- Container `docx-replace-worker --replace-local` replaced the same two sample DOCX text nodes.
- `scripts/dev/smoke-docx-replace-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The live smoke event contained `event_type=stage.completed`, `stage=docx_replace`, and output key `2026-01-21/12345678/replacesmoke1/04_replace/translated.docx`.
- `git diff --check` passes.

Commit:

- Implementation committed as `1a1abe2` with message `feat: add docx replace artifact flow`.

Next recommended step:

- Continue `feat/pdf-docx-pipeline` with `docx_export`: read `04_replace/translated.docx`, write `05_export/final.docx` and an initial final PDF artifact path, and publish only worker stage events.

## 2026-06-10 23:41 KST - docx_export artifact/event flow

Done:

- Continued branch `feat/pdf-docx-pipeline`.
- Implemented `libreoffice-worker` runtime package for the `docx_export` stage.
- Added `libreoffice-worker --export-local` for host/container validation.
- Added `libreoffice-worker --consume` to consume `q.commands.docx_export`, download `04_replace/translated.docx`, upload `05_export/final.docx` and `05_export/final.pdf`, and publish `stage.completed` or `stage.failed`.
- Supported both `input_type=pdf` and `input_type=docx` for the DOCX export route.
- Added default placeholder PDF mode through `DOCX_EXPORT_PDF_MODE=placeholder`.
- Added a future LibreOffice path through `DOCX_EXPORT_PDF_MODE=libreoffice` and `LIBREOFFICE_BINARY`.
- Added `scripts/dev/smoke-docx-export-live.sh` for disposable Docker MinIO/RabbitMQ live validation.
- Did not install LibreOffice in the runtime image, implement real PDF conversion by default, generate marker DOCX, implement pdf2hwpx, implement HWPX export, PostgreSQL persistence, or Helm changes in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 66 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- Host `libreoffice-worker --export-local` copied a sample translated DOCX and wrote a placeholder PDF.
- Container `libreoffice-worker --export-local` copied the same sample translated DOCX and wrote a placeholder PDF.
- `scripts/dev/smoke-docx-export-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The live smoke event contained `event_type=stage.completed`, `stage=docx_export`, and output keys `2026-01-21/12345678/exportsmoke1/05_export/final.docx` and `2026-01-21/12345678/exportsmoke1/05_export/final.pdf`.
- `git diff --check` passes.

Commit:

- Implementation committed as `94b9ff4` with message `feat: add docx export artifact flow`.

Next recommended step:

- Continue `feat/pdf-docx-pipeline` with `docx_marker`: read `05_export/final.docx`, replace spaces with `¡`, write `05_export/marker.docx`, and publish only worker stage events.

## 2026-06-11 00:13 KST - docx_marker artifact/event flow

Done:

- Continued branch `feat/pdf-docx-pipeline`.
- Implemented `libreoffice-worker` `docx_marker` runtime mode.
- Added `libreoffice-worker --mark-local` for host/container validation.
- Added `libreoffice-worker --consume-marker` to consume `q.commands.docx_marker`, download `05_export/final.docx`, upload `05_export/marker.docx`, and publish `stage.completed` or `stage.failed`.
- Supported both `input_type=pdf` and `input_type=docx` for the DOCX marker route.
- Added default marker token `DOCX_MARKER_TOKEN=¡`.
- Added `scripts/dev/smoke-docx-marker-live.sh` for disposable Docker MinIO/RabbitMQ live validation.
- Did not implement `pdf2hwpx`, HWPX route processing, PostgreSQL persistence, Helm changes, or real LibreOffice PDF conversion in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 71 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- Host `libreoffice-worker --mark-local` replaced spaces in a sample DOCX with `¡`.
- Container `libreoffice-worker --mark-local` replaced spaces in the same sample DOCX with `¡`.
- `scripts/dev/smoke-docx-marker-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The live smoke event contained `event_type=stage.completed`, `stage=docx_marker`, and output key `2026-01-21/12345678/markersmoke1/05_export/marker.docx`.
- `git diff --check` passes.

Commit:

- Implementation committed as `b0ae05f` with message `feat: add docx marker artifact flow`.

Next recommended step:

- Continue `feat/pdf-docx-pipeline` with `pdf2hwpx`: read `05_export/marker.docx`, write `06_hwpx/final.hwpx` with a placeholder/stub until the real custom `pdf2hwpx` library is available, and publish only worker stage events.

## 2026-06-11 16:49 KST - pdf2hwpx placeholder artifact/event flow

Done:

- Continued branch `feat/pdf-docx-pipeline`.
- Implemented `pdf2hwpx-worker` runtime package.
- Added placeholder HWPX generation from `05_export/marker.docx` to `06_hwpx/final.hwpx`.
- Added `pdf2hwpx-worker --generate-local` for host/container validation.
- Added `pdf2hwpx-worker --consume` to consume `q.commands.pdf2hwpx`, download `05_export/marker.docx`, upload `06_hwpx/final.hwpx`, and publish `stage.completed` or `stage.failed`.
- Supported both `input_type=pdf` and `input_type=docx` for the PDF/DOCX HWPX placeholder route.
- Added `scripts/dev/smoke-pdf2hwpx-live.sh` for disposable Docker MinIO/RabbitMQ live validation.
- Did not implement the real custom `pdf2hwpx` library, HWPX route processing, PostgreSQL persistence, Helm changes, real LibreOffice PDF conversion, or email sending in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 76 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- Host `pdf2hwpx-worker --generate-local` generated a placeholder HWPX zip from a sample marker DOCX.
- Container `pdf2hwpx-worker --generate-local` generated the same placeholder HWPX zip structure.
- `scripts/dev/smoke-pdf2hwpx-live.sh` passes with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- The live smoke event contained `event_type=stage.completed`, `stage=pdf2hwpx`, and output key `2026-01-21/12345678/hwpxsmoke1/06_hwpx/final.hwpx`.
- `git diff --check` passes.

Commit:

- Implementation committed as `060517b` with message `feat: add pdf2hwpx placeholder artifact flow`.

Next recommended step:

- Continue `feat/pdf-docx-pipeline` with `email_send`: add a safe local/mock email worker flow that checks `job-service` sendability before sending and publishes only worker stage events.

## 2026-06-11 20:09 KST - email provider contract replan

Done:

- Stopped feature implementation work and created branch `docs/email-provider-contract`.
- Updated project plan, architecture, pipeline, and contracts so `email-worker` is provider-backed instead of SMTP-fixed.
- Added `docs/EMAIL_PROVIDER.md` with the MailProvider interface, mock behavior, sendability gate, Helm values shape, and implementation roadmap.
- Recorded that local development should use `EMAIL_PROVIDER=mock`.
- Recorded that military/internal mail API support belongs behind a later `EMAIL_PROVIDER=military_api` adapter.
- Documented `email_send` command shape, completed/failed events, and `email_report.json` minimal schema.
- No runtime email-worker implementation was added on this documentation branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 76 tests.
- `scripts/dev/smoke-services.sh` passes.
- `git diff --check` passes.

Commit:

- Email provider contract documentation committed as `245b78f` with message `docs: add pluggable email provider contract`.

Next recommended step:

- Start `feat/email-worker-provider` from this checkpoint and implement the mock provider flow: consume `q.commands.email_send`, call `job-service` sendability, write MinIO `reports/email_report.json`, and publish only `stage.completed` or `stage.failed`.

## 2026-06-11 20:53 KST - email-worker mock provider artifact/event flow

Done:

- Created branch `feat/email-worker-provider`.
- Added shared config fields for `JOB_SERVICE_URL`, `EMAIL_PROVIDER`, email API base URL/timeout, sender, send-enabled flag, and email API secret placeholders.
- Implemented `email-worker` runtime package with `MailProvider`, `MockMailProvider`, `--send-local`, and `--consume`.
- Added HTTP `job-service` sendability client.
- Updated `job-service` sendability response to include `input_type`, `user_id`, `object_prefix`, and artifact keys needed by `email-worker`.
- Implemented mock email report upload to `{object_prefix}/reports/email_report.json`.
- Implemented `stage.completed` and `stage.failed` events for `email_send`.
- Added `scripts/dev/smoke-email-worker-live.sh` for disposable Docker MinIO/RabbitMQ/fake-job-service validation.
- Did not implement SMTP, military/internal mail API, Helm chart wiring, PostgreSQL persistence, or full E2E route smoke in this branch.

Verified:

- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 83 tests.
- `scripts/dev/smoke-services.sh` passes.
- `scripts/dev/build-images.sh` passes for all 8 service images.
- `scripts/dev/smoke-images.sh` passes for all 8 service images.
- `python3 services/email-worker/worker.py --send-local ...` writes a local mock `email_report.json`.
- `scripts/dev/smoke-email-worker-live.sh` passes and verifies the MinIO report plus `stage.completed` event.
- `git diff --check` passes.

Commit:

- Email worker mock provider implementation committed as `5d2a9fe` with message `feat: add email-worker mock provider flow`.

Next recommended step:

- Start `feat/hwpx-rhwp-pipeline`: implement the first HWPX route skeleton and validate/document `rhwp` plus LibreOffice H2O/HWPX availability.

## 2026-06-11 21:29 KST - HWPX route skeleton

Done:

- Created branch `feat/hwpx-rhwp-pipeline`.
- Added `hwpx-worker` service with Dockerfile, smoke entrypoint, local sample creation, local extract/replace commands, and RabbitMQ consume modes for `hwpx_extract` and `hwpx_replace`.
- Added local zip/XML HWPX stub for text unit extraction and replacement while real `rhwp` is unavailable.
- Extended `translate-worker` so `input_type=hwpx` uses `hwpx_translate` and `q.commands.hwpx_translate`.
- Extended `libreoffice-worker` with `hwpx_export` mode to copy final HWPX and write placeholder final DOCX/PDF artifacts.
- Added config flags `HWPX_RHWP_ENABLED` and `HWPX_H2O_EXPORT_ENABLED`, both defaulting to `false`.
- Added `scripts/dev/smoke-hwpx-local.sh`.
- Updated scripts and smoke tests to include the new `hwpx-worker` image.
- Documented that real `rhwp` and LibreOffice H2O/HWPX support are still validation items.

Verified:

- `rhwp` is not installed in the current local Python environment.
- `soffice`/`libreoffice` were not found in PATH.
- `python3 -m compileall -q services tests` passes.
- `python3 -m unittest discover -s tests` passes with 94 tests.
- `scripts/dev/smoke-services.sh` passes for all 9 services.
- `scripts/dev/smoke-hwpx-local.sh` passes.
- `git diff --check` passes.
- `scripts/dev/build-images.sh` passes for all 9 service images.
- `scripts/dev/smoke-images.sh` passes for all 9 service images.
- Docker Hub push was not attempted because `docker info --format '{{.Username}}'` did not report a logged-in username.

Commit:

- Implementation committed as `1264b42` with message `feat: add hwpx route skeleton`.

Next recommended step:

- Either add a live MinIO/RabbitMQ HWPX route smoke on `feat/hwpx-rhwp-pipeline`, or start `feat/helm-local-stack` and wire all 9 services plus the HWPX config flags into Helm.

## 2026-06-11 22:38 KST - Current PC environment bootstrap blocked

Done:

- Read the continuation docs before changing local state.
- Fetched `origin`, created local `feat/hwpx-rhwp-pipeline` tracking `origin/feat/hwpx-rhwp-pipeline`, and created `test/hwpx-live-minio-rabbitmq-smoke`.
- Confirmed the current Git version is `2.17.1`; it does not support `git branch --show-current`, so `git rev-parse --abbrev-ref HEAD` was used to confirm the current branch.
- Ran the requested local tool checks.
- Stopped before HWPX live MinIO/RabbitMQ smoke implementation because this PC cannot currently run Docker/kubectl/k3d validation.

Verified:

- Current branch is `test/hwpx-live-minio-rabbitmq-smoke`.
- Current distro is Ubuntu 18.04 on WSL version 1; `wsl.exe -l -v` reports `Ubuntu-18.04` as `VERSION 1`.
- Docker Desktop WSL helper is present at `/mnt/c/Program Files/Docker/Docker/resources/bin/docker`, but `docker version` and `docker ps` fail with the Docker Desktop WSL 1 warning.
- `kubectl`, `helm`, `k3d`, `kind`, and native `k3s` are not found in PATH.
- `scripts/dev/check-env.sh` fails with Docker server not reachable, `kubectl` missing, Helm missing, and k3d missing.
- `python3` is Python `3.6.9`, which cannot compile the project because it does not support `from __future__ import annotations`.
- `python3.10` is installed and can run host-side checks.
- `python3.10 -m compileall -q services tests` passes.
- `python3.10 -m unittest discover -s tests` passes with 94 tests.
- `PYTHON_BIN=python3.10 scripts/dev/smoke-services.sh` passes for all 9 services.
- `PYTHON_BIN=python3.10 scripts/dev/smoke-hwpx-local.sh` passes.
- `git diff --check` passed before documentation edits.

Not run:

- `scripts/dev/bootstrap-cluster.sh`
- `scripts/dev/smoke-test.sh`
- `scripts/dev/build-images.sh`
- `scripts/dev/smoke-images.sh`
- Existing live MinIO/RabbitMQ smoke scripts
- New HWPX live MinIO/RabbitMQ smoke implementation

Root cause:

- The active distro is WSL 1, while Docker Desktop WSL integration requires WSL 2.
- The current Ubuntu 18.04 environment does not have project Kubernetes tools installed in PATH.
- The default `python3` points to Python 3.6 instead of a supported Python 3.10+ interpreter.

Recovery commands for the next continuation:

```powershell
wsl --shutdown
wsl --set-version Ubuntu-18.04 2
wsl -l -v
```

Then enable Docker Desktop WSL integration for `Ubuntu-18.04`, reopen the distro, and run:

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

Install or restore `kubectl` in PATH, then rerun:

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

Commit:

- Documentation-only environment bootstrap record; see the commit created from this entry.

Next recommended step:

- Repair this PC's local development environment first. Only after Docker, kubectl, Helm, k3d, and the existing image smoke checks pass, continue with `scripts/dev/smoke-hwpx-live.sh` or the repository's final chosen HWPX live smoke script name.

## 2026-06-11 22:52 KST - Ubuntu 24.04 WSL2 auto-setup blocked

Done:

- Re-read the required continuation docs before taking further environment actions.
- Confirmed the active project distro is still Ubuntu 18.04 on WSL version 1.
- Confirmed Docker Desktop WSL distros are running on WSL version 2.
- Confirmed Docker, kubectl, Helm, and k3d still cannot be used from the active distro.
- Attempted a non-launching Ubuntu 24.04 WSL install path before any implementation work.

Verified:

- `/mnt/c/Windows/System32/wsl.exe -l -v` lists `Ubuntu-18.04` as the default running distro with `VERSION 1`.
- `/mnt/c/Windows/System32/wsl.exe --status` reports default WSL version 2 and default distribution `Ubuntu-18.04`.
- `cat /etc/os-release` reports Ubuntu `18.04.6 LTS`.
- `uname -a` reports the WSL1-style `4.4.0-26100-Microsoft` kernel.
- `python3 --version` reports Python `3.6.9`.
- `docker version` and `docker ps` still fail with Docker Desktop's WSL1 distro warning.
- `kubectl`, `helm`, and `k3d` are still not found in PATH.
- `wsl --install Ubuntu-24.04 --no-launch --web-download` fails with `WSL_E_DISTRO_NOT_FOUND`.
- `wsl --install Ubuntu --no-launch --web-download` ran for over two minutes with no output, did not register a new distro, and was terminated.

Not run:

- `sudo apt update` or package installation inside Ubuntu 24.04, because Ubuntu 24.04 is not available from this session yet.
- Docker Desktop WSL integration validation for Ubuntu 24.04.
- `scripts/dev/check-env.sh`, image builds, image smokes, or HWPX live smoke implementation.

Root cause:

- This Windows WSL install does not expose a direct `Ubuntu-24.04` distro name through `wsl --list --online`.
- The generic `Ubuntu` web-download install path did not complete from this Codex-controlled WSL1 session.
- Continuing in Ubuntu 18.04 WSL1 would violate the requested recovery direction and still cannot run Docker Desktop integration.

What must happen manually:

- Install or enable an Ubuntu 24.04 WSL2 distro from Windows.
- Enable Docker Desktop WSL Integration for that Ubuntu 24.04 distro.
- Reopen this repository from the Ubuntu 24.04 WSL2 distro.

Commit:

- Documentation-only Ubuntu 24.04 WSL2 recovery blocker record; see the commit created from this entry.

Next recommended step:

- After the Ubuntu 24.04 WSL2 distro is available, rerun the environment validation sequence from that distro before doing any HWPX live smoke implementation.

## 2026-06-11 23:56 KST - Ubuntu 24.04 WSL2 partial recovery, Docker blocked

Done:

- Re-read required continuation docs.
- Confirmed current branch is `test/hwpx-live-minio-rabbitmq-smoke`.
- Confirmed the active Windows WSL default distro is now `Ubuntu-24.04` on WSL version 2.
- Ran validation commands inside Ubuntu 24.04 through `wsl.exe -d Ubuntu-24.04` because the Codex shell remained attached to Ubuntu 18.04 WSL1.
- Confirmed Ubuntu 24.04, WSL2 kernel, Python 3.12.3, and GitHub SSH authentication.
- Installed Helm and k3d into `/home/peto/.local/bin` without sudo.
- Started Docker Desktop from Windows once and observed one successful `docker version` / `docker ps` result.
- Stopped before Python/image/k3d/HWPX smoke validation because Docker Desktop WSL integration became unstable and `docker ps` no longer succeeded.

Verified:

- `cat /etc/os-release` inside Ubuntu 24.04 reports `Ubuntu 24.04.4 LTS`.
- `uname -a` inside Ubuntu 24.04 reports WSL2 kernel `6.18.33.1-microsoft-standard-WSL2`.
- `python3 --version` reports Python `3.12.3`.
- `git status` reports clean worktree on `test/hwpx-live-minio-rabbitmq-smoke`.
- `ssh -T git@github.com || true` authenticates as `Petooooo`.
- `git fetch --all --prune` succeeds.
- `git pull --ff-only` fails because local `test/hwpx-live-minio-rabbitmq-smoke` has no upstream tracking branch; no remote `origin/test/hwpx-live-minio-rabbitmq-smoke` was listed.
- `sudo -n true` fails with `sudo: a password is required`, so sudo-based installs were not attempted.
- `helm version` passes after installing Helm `v3.21.0` into `~/.local/bin`.
- `k3d version` passes after installing k3d `v5.9.0` into `~/.local/bin`.

Blocked:

- `docker version` initially failed because the Docker daemon was not running.
- Docker Desktop was started, after which `docker version` and `docker ps` passed once.
- Subsequent Docker commands failed because `/usr/bin/docker -> /mnt/wsl/docker-desktop/cli-tools/usr/bin/docker` segfaulted.
- `curl --unix-socket /var/run/docker.sock http://localhost/_ping` fails with `Couldn't connect to server`.
- `wsl -l -v` no longer shows `docker-desktop` running while the Docker socket is unresponsive.
- `kubectl version --client` returned `Input/output error` from the Docker Desktop CLI-tools symlink `/usr/local/bin/kubectl`.

Not run:

- `python3 -m compileall -q services tests`
- `python3 -m unittest discover -s tests`
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`
- `scripts/dev/check-env.sh`
- `scripts/dev/build-images.sh`
- `scripts/dev/smoke-images.sh`
- `scripts/dev/bootstrap-cluster.sh`
- `scripts/dev/smoke-test.sh`
- HWPX live MinIO/RabbitMQ smoke implementation

What must happen manually:

- Open Docker Desktop on Windows.
- Confirm the Docker engine is running.
- Enable Docker Desktop WSL Integration for `Ubuntu-24.04` if it is not enabled.
- Apply & Restart Docker Desktop if needed.
- Re-run `docker version` and `docker ps` from Ubuntu 24.04 until they are stable.

Commit:

- Documentation-only Ubuntu 24.04/Docker blocker record; see the commit created from this entry.

Next recommended step:

- Resume from Docker validation only after `docker ps` reliably succeeds inside Ubuntu 24.04. Do not implement HWPX live smoke before that.

## 2026-06-12 02:04 KST - Ubuntu 24.04 WSL2 recovery and HWPX live smoke

Done:

- Resumed from the prior Docker Desktop WSL integration blocker after the repo was opened from `Ubuntu-24.04` WSL2 at `/mnt/d/Workspaces/Codex/file-translation`.
- Confirmed current branch is `test/hwpx-live-minio-rabbitmq-smoke`.
- Confirmed GitHub SSH authentication succeeds.
- Confirmed Docker Desktop WSL integration is stable from Ubuntu 24.04.
- Rebuilt and smoke-tested all 9 project service images locally.
- Created local k3d cluster `file-translation-dev` because no existing k3d cluster was present.
- Verified kubectl context `k3d-file-translation-dev`, namespace `file-translation`, Ready nodes, CoreDNS, and cluster DNS.
- Verified live disposable MinIO/RabbitMQ access with `scripts/dev/smoke-pdf2hwpx-live.sh`.
- Verified disposable PostgreSQL startup and query access with `postgres:16-alpine`.
- Added `scripts/dev/smoke-hwpx-live.sh`.
- Validated HWPX live extract-to-translate command/event/artifact flow through real MinIO and RabbitMQ.
- Did not do Helm chart work.
- Did not implement real `rhwp`, real LibreOffice H2O export, or full job-service orchestration.

Verified:

- `cat /etc/os-release`: Ubuntu `24.04.4 LTS`.
- `uname -a`: WSL2 kernel `6.18.33.1-microsoft-standard-WSL2`.
- `python3 --version`: Python `3.12.3`.
- `docker version` and `docker ps`: passed with Docker Desktop `24.0.6`.
- `kubectl version --client`: client `v1.28.2`.
- `helm version`: `v3.21.0`.
- `k3d version`: `v5.9.0`.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 94 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/bootstrap-cluster.sh`: passed and created `file-translation-dev`.
- `scripts/dev/smoke-test.sh`: passed.
- `scripts/dev/smoke-pdf2hwpx-live.sh`: passed with MinIO `RELEASE.2025-02-07T23-21-09Z` and RabbitMQ `3.13-management`.
- Disposable PostgreSQL smoke using `postgres:16-alpine`: passed with `select 1`.
- `scripts/dev/smoke-hwpx-live.sh`: passed; verified `hwpx_extract` wrote `02_extract/text_units.json`, emitted `stage.completed`, then `hwpx_translate` wrote `03_translate/translated_units.json`, emitted progress, and emitted `stage.completed`.

Notes:

- `git pull --ff-only` still reports no upstream tracking branch for local `test/hwpx-live-minio-rabbitmq-smoke`; no remote branch was pulled and no push was performed.
- PostgreSQL is not yet wired into a project service or Kubernetes local stack. The validation here confirms local disposable PostgreSQL accessibility only.

Commit:

- `test: add hwpx live minio rabbitmq smoke`

Next recommended step:

- Extend the HWPX live smoke only after deciding whether to cover `hwpx_replace`/`hwpx_export` placeholders or job-service orchestration next. Keep Helm chart work until pipeline and smoke validation are stable.

## 2026-06-12 08:00 KST - job-service orchestration live smoke

Done:

- Created branch `test/job-service-orchestration-live-smoke` from `test/hwpx-live-minio-rabbitmq-smoke` at `91e9658`.
- Added `JOB_SERVICE_REPOSITORY=postgres` while preserving `memory` as the default.
- Added a minimal PostgreSQL repository for `job-service` that persists the job aggregate as JSONB in a `jobs` table.
- Kept `JOB_SERVICE_COMMAND_PUBLISHER=memory` and `JOB_SERVICE_EVENT_CONSUMER=disabled` defaults unchanged.
- Added `psycopg[binary]==3.2.3` to the job-service image runtime.
- Added `scripts/dev/smoke-job-orchestration-live.sh`.
- The new smoke runs disposable MinIO, RabbitMQ, PostgreSQL, and `job-service`.
- Verified `job-service` consumes RabbitMQ `stage.completed` events, updates PostgreSQL job state, and publishes the next command through RabbitMQ.
- Verified a cancelled DOCX job does not publish the next command.
- Did not do Helm chart work.
- Did not change worker behavior; workers still publish only events/progress and never enqueue the next stage.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-hwpx-live.sh`: passed.
- `scripts/dev/smoke-test.sh`: passed against k3d `file-translation-dev`.
- `scripts/dev/smoke-job-orchestration-live.sh`: passed.

Live orchestration scenarios:

- `pdf` job: `pdf2docx stage.completed` -> PostgreSQL `current_stage=docx_extract` -> `q.commands.docx_extract`.
- `docx` job: `docx_extract stage.completed` -> PostgreSQL `current_stage=docx_translate` -> `q.commands.docx_translate`.
- `hwpx` job: `hwpx_extract stage.completed` -> PostgreSQL `current_stage=hwpx_translate` -> `q.commands.hwpx_translate`.
- cancelled `docx` job: `docx_extract stage.completed` -> PostgreSQL `current_stage=cancelled` -> no `q.commands.docx_translate`.

Notes:

- The PostgreSQL repository intentionally uses a JSONB job aggregate for this live smoke. Normalized `job_stages` and outbox tables remain future work.
- `git pull --ff-only` on `test/hwpx-live-minio-rabbitmq-smoke` still has no upstream tracking branch and no remote `origin/test/hwpx-live-minio-rabbitmq-smoke`; the new branch was created from local `91e9658`.

Commit:

- `test: add job-service orchestration live smoke`

Next recommended step:

- Extend orchestration live smoke to a longer route path only after deciding whether to include placeholder `hwpx_replace`/`hwpx_export` and `email_send`. Keep Helm chart work deferred until smoke coverage is stable.

## 2026-06-12 KST - HWPX replace/export live smoke

Done:

- Created branch `test/hwpx-replace-export-live-smoke` from local `test/job-service-orchestration-live-smoke` at `44804c1`.
- Added `scripts/dev/smoke-hwpx-replace-export-live.sh`.
- Kept worker behavior unchanged: workers publish `stage.completed` / `stage.failed` / progress events only; job-service publishes the next command.
- Updated job-service command publishing so the first route command includes the job's `input_object_key` when known.
- The new smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `hwpx-worker` extract/replace consumers, `translate-worker --consume-hwpx`, and `libreoffice-worker --consume-hwpx-export`.
- Verified the longer placeholder HWPX route through `hwpx_extract -> hwpx_translate -> hwpx_replace -> hwpx_export`.
- Verified cancelled HWPX job behavior before starting workers: a `hwpx_extract stage.completed` event moves the job to `cancelled` and does not publish `q.commands.hwpx_translate`.
- Verified PostgreSQL `jobs.payload` JSONB directly after the smoke.
- Did not do Helm chart work.
- Did not implement real `rhwp`, real LibreOffice H2O export, `pdf2hwpx`, or email provider behavior.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-hwpx-live.sh`: passed.
- `scripts/dev/smoke-job-orchestration-live.sh`: passed.
- `bash -n scripts/dev/smoke-hwpx-replace-export-live.sh`: passed.
- `scripts/dev/smoke-hwpx-replace-export-live.sh`: passed.

Live HWPX replace/export smoke details:

- `job-service` created an HWPX job with a pre-uploaded MinIO input key and published the initial `hwpx_extract` command with `input_object_key`.
- `hwpx-worker --consume-extract` wrote `02_extract/text_units.json`.
- `job-service` consumed the extract event and published `q.commands.hwpx_translate`.
- `translate-worker --consume-hwpx` wrote `03_translate/translated_units.json` using the mock provider.
- `job-service` consumed the translate event and published `q.commands.hwpx_replace`.
- `hwpx-worker --consume-replace` wrote `04_replace/translated.hwpx`.
- `job-service` consumed the replace event and published `q.commands.hwpx_export`.
- `libreoffice-worker --consume-hwpx-export` wrote placeholder `05_export/final.docx`, placeholder `05_export/final.pdf`, and `06_hwpx/final.hwpx`.
- PostgreSQL state reached `current_stage=email_send`; `hwpx_extract`, `hwpx_translate`, `hwpx_replace`, and `hwpx_export` stages were completed; final HWPX/DOCX/PDF keys were recorded.

Current limits:

- HWPX extract/replace remains a zip/XML skeleton, not real `rhwp`.
- HWPX export still uses placeholder DOCX/PDF output with `HWPX_H2O_EXPORT_ENABLED=false`.
- The smoke stops at the sendable `email_send` stage; it does not send email or mark the whole job completed.

Next recommended step:

- Decide whether the next live smoke should cover `email_send` sendability/end-state or begin preparing the local Helm chart only after the current smoke suite remains stable.

## 2026-06-12 KST - email_send sendability/end-state live smoke

Done:

- Added `scripts/dev/smoke-email-end-state-live.sh`.
- Added a startup retry around the PostgreSQL JSONB repository schema initialization so disposable Docker DNS/readiness races do not strand `job-service` before `/readyz`.
- The new smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, and `email-worker`.
- The smoke uses synthetic upstream HWPX `stage.completed` events to focus on `email_send`; the actual HWPX worker artifact chain remains covered by `scripts/dev/smoke-hwpx-replace-export-live.sh`.
- Verified `job-service` reaches `current_stage=email_send`, publishes `q.commands.email_send`, `email-worker` consumes the command, calls `job-service` sendability, writes `reports/email_report.json` to MinIO, publishes `email_send stage.completed`, and `job-service` marks the job `completed`.
- Verified direct PostgreSQL JSONB terminal state after the smoke.
- Did not do Helm chart work.
- Did not implement real email provider delivery, SMTP, internal mail API, real `rhwp`, or real LibreOffice H2O export.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-email-worker-live.sh`: passed.
- `scripts/dev/smoke-hwpx-live.sh`: passed.
- `scripts/dev/smoke-job-orchestration-live.sh`: passed.
- `scripts/dev/smoke-hwpx-replace-export-live.sh`: passed.
- `bash -n scripts/dev/smoke-email-end-state-live.sh`: passed.
- `scripts/dev/smoke-email-end-state-live.sh`: passed.

Live email end-state smoke details:

- `job-service` ran with `JOB_SERVICE_REPOSITORY=postgres`, `JOB_SERVICE_COMMAND_PUBLISHER=rabbitmq`, and `JOB_SERVICE_EVENT_CONSUMER=rabbitmq`.
- Upstream synthetic HWPX completion events populated final artifact keys and moved the job to `email_send`.
- `email-worker` used the minimal command shape and fetched sendability from `job-service`; attachments came from job-service artifacts.
- MinIO contained `reports/email_report.json` with mock provider status `sent` and no secret-like fields.
- PostgreSQL persisted `status=completed`, `current_stage=completed`, completed `email_send`, and the `email_report` artifact key.
- A post-completion sendability check returned `sendable=false`, as expected for terminal jobs.

Current limits:

- This smoke does not rerun actual upstream workers; it deliberately isolates email sendability/end-state.
- Email delivery remains mock-only.
- The PostgreSQL repository still uses the JSONB aggregate smoke table, not a final normalized schema or outbox.

Next recommended step:

- With HWPX replace/export and email end-state smoke coverage stable, the next major item can be Helm/local-stack preparation unless another route-level live smoke gap is identified first.

## 2026-06-12 KST - HWPX route-level E2E smoke

Done:

- Created branch `test/hwpx-route-e2e-smoke` from the latest email end-state smoke commit.
- Added `scripts/dev/smoke-hwpx-route-e2e.sh`.
- The new smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `hwpx-worker` extract/replace consumers, `translate-worker --consume-hwpx`, `libreoffice-worker --consume-hwpx-export`, and `email-worker`.
- Verified one actual HWPX route-level flow from `job-service` create API through every worker to terminal `completed`.
- Verified cancellation gates before workers start:
  - mid-route cancel: `hwpx_extract stage.completed` after cancel moves the job to `cancelled` and does not publish `hwpx_translate`
  - email-stage cancel: after synthetic upstream completion reaches `email_send`, `cancel_requested` makes sendability false and no email report is written
- Verified no stale RabbitMQ command messages remain after the successful HWPX E2E job.
- Did not do Helm chart work.
- Did not implement real `rhwp`, real LibreOffice H2O export, `pdf2hwpx`, DOCX/PDF E2E, or real email provider delivery.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-hwpx-live.sh`: passed.
- `scripts/dev/smoke-job-orchestration-live.sh`: passed.
- `scripts/dev/smoke-hwpx-replace-export-live.sh`: passed.
- `scripts/dev/smoke-email-end-state-live.sh`: passed.
- `bash -n scripts/dev/smoke-hwpx-route-e2e.sh`: passed.
- `scripts/dev/smoke-hwpx-route-e2e.sh`: passed.

HWPX route E2E details:

- `job-service` created an HWPX job and published the initial `hwpx_extract` command.
- `hwpx-worker --consume-extract` created `02_extract/text_units.json`.
- `job-service` consumed the extract event and published `hwpx_translate`.
- `translate-worker --consume-hwpx` created `03_translate/translated_units.json`.
- `job-service` consumed the translate event and published `hwpx_replace`.
- `hwpx-worker --consume-replace` created `04_replace/translated.hwpx`.
- `job-service` consumed the replace event and published `hwpx_export`.
- `libreoffice-worker --consume-hwpx-export` created placeholder final DOCX/PDF and final HWPX artifacts.
- `job-service` consumed the export event and published `email_send`.
- `email-worker` consumed `email_send`, called job-service sendability, wrote `reports/email_report.json`, and published `email_send stage.completed`.
- `job-service` consumed the email event and persisted `status=completed`, `current_stage=completed`.

Current limits:

- HWPX parsing/replacement is still the local zip/XML stub.
- HWPX export still uses placeholder DOCX/PDF output with `HWPX_H2O_EXPORT_ENABLED=false`.
- Email delivery remains mock-only.
- PostgreSQL persistence remains the JSONB aggregate smoke table; no outbox or normalized schema was added.

Follow-up:

- DOCX route-level E2E coverage was added next in the following section. Keep Helm/local-stack work deferred until HWPX, DOCX, and PDF E2E smoke coverage is stable.

## 2026-06-12 KST - DOCX route-level E2E smoke

Done:

- Created branch `test/docx-route-e2e-smoke` from `test/hwpx-route-e2e-smoke`.
- Added `scripts/dev/smoke-docx-route-e2e.sh`.
- The new smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `docx-extract-worker`, `translate-worker`, `docx-replace-worker`, `libreoffice-worker` export/marker consumers, `pdf2hwpx-worker`, and `email-worker`.
- Verified one actual DOCX route-level flow from `job-service` create API through every worker to terminal `completed`.
- Verified cancellation gates before workers start:
  - mid-route cancel: `docx_extract stage.completed` after cancel moves the job to `cancelled` and does not publish `docx_translate`
  - email-stage cancel: after synthetic upstream completion reaches `email_send`, `cancel_requested` makes sendability false and no email report is written
- Verified no stale RabbitMQ command messages remain after the successful DOCX E2E job.
- Hardened PostgreSQL readiness checks in `scripts/dev/smoke-hwpx-replace-export-live.sh` and `scripts/dev/smoke-job-orchestration-live.sh` after validation exposed a flaky final `pg_isready` check.
- Did not do Helm chart work.
- Did not implement real LibreOffice PDF export, real `pdf2hwpx`, PDF E2E, or real email provider delivery.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-hwpx-live.sh`: passed.
- `scripts/dev/smoke-job-orchestration-live.sh`: passed after readiness hardening.
- `scripts/dev/smoke-hwpx-replace-export-live.sh`: passed after readiness hardening.
- `scripts/dev/smoke-email-end-state-live.sh`: passed.
- `scripts/dev/smoke-hwpx-route-e2e.sh`: passed.
- `bash -n scripts/dev/smoke-docx-route-e2e.sh`: passed.
- `scripts/dev/smoke-docx-route-e2e.sh`: passed.

DOCX route E2E details:

- `job-service` created a DOCX job and published the initial `docx_extract` command.
- `docx-extract-worker --consume` created `02_extract/text_units.json`.
- `job-service` consumed the extract event and published `docx_translate`.
- `translate-worker --consume` created `03_translate/translated_units.json`.
- `job-service` consumed the translate event and published `docx_replace`.
- `docx-replace-worker --consume` created `04_replace/translated.docx`.
- `job-service` consumed the replace event and published `docx_export`.
- `libreoffice-worker --consume` copied translated DOCX to `05_export/final.docx` and wrote placeholder `05_export/final.pdf`.
- `job-service` consumed the export event and published `docx_marker`.
- `libreoffice-worker --consume-marker` created `05_export/marker.docx` with the marker token.
- `job-service` consumed the marker event and published `pdf2hwpx`.
- `pdf2hwpx-worker --consume` created placeholder `06_hwpx/final.hwpx`.
- `job-service` consumed the HWPX event and published `email_send`.
- `email-worker` consumed `email_send`, called job-service sendability, wrote `reports/email_report.json`, and published `email_send stage.completed`.
- `job-service` consumed the email event and persisted `status=completed`, `current_stage=completed`.

Current limits:

- DOCX extraction/replacement still covers the MVP `word/document.xml` text-run path only.
- DOCX export still uses `DOCX_EXPORT_PDF_MODE=placeholder`.
- `pdf2hwpx` still writes a placeholder HWPX package containing `placeholder.json` and `source/marker.docx`.
- Email delivery remains mock-only.
- PostgreSQL persistence remains the JSONB aggregate smoke table; no outbox or normalized schema was added.

Follow-up:

- PDF route-level E2E coverage was added next in the following section. Helm/local-stack work remained deferred until HWPX, DOCX, and PDF E2E smoke coverage was stable.

## 2026-06-12 KST - PDF route-level E2E smoke

Done:

- Created branch `test/pdf-route-e2e-smoke` from `test/docx-route-e2e-smoke`.
- Added `scripts/dev/smoke-pdf-route-e2e.sh`.
- The new smoke starts disposable MinIO, RabbitMQ, PostgreSQL, `job-service`, `pdf2docx-worker`, `docx-extract-worker`, `translate-worker`, `docx-replace-worker`, `libreoffice-worker` export/marker consumers, `pdf2hwpx-worker`, and `email-worker`.
- Verified one actual PDF route-level flow from `job-service` create API through every worker to terminal `completed`.
- Verified the PDF route starts with the custom static anchored `pdf2docx` path:
  - sample PDF generation uses `petoo/pdf2docx:0.5.13-py311-static`
  - `pdf2docx-worker` consumes `q.commands.pdf2docx`
  - `PDF2DOCX_ENABLE_REPORTS=true` writes `01_pdf2docx/converted.docx`, `reports/pdf2docx.report.json`, and `reports/pdf2docx.report.md`
- Verified cancellation gates before workers start:
  - mid-route cancel: `pdf2docx stage.completed` after cancel moves the job to `cancelled` and does not publish `docx_extract`
  - email-stage cancel: after synthetic upstream completion reaches `email_send`, `cancel_requested` makes sendability false and no email report is written
- Verified no stale RabbitMQ command messages remain after the successful PDF E2E job.
- Did not do Helm chart work.
- Did not implement real LibreOffice PDF export, real `pdf2hwpx`, or real email provider delivery.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-hwpx-route-e2e.sh`: passed.
- `scripts/dev/smoke-docx-route-e2e.sh`: passed.
- `scripts/dev/smoke-pdf2docx-live.sh`: passed.
- `bash -n scripts/dev/smoke-pdf-route-e2e.sh`: passed.
- `scripts/dev/smoke-pdf-route-e2e.sh`: passed.

PDF route E2E details:

- `job-service` created a PDF job and published the initial `pdf2docx` command.
- `pdf2docx-worker --consume` invoked the static anchored converter and created `01_pdf2docx/converted.docx` plus JSON/Markdown reports.
- `job-service` consumed the conversion event and published `docx_extract`.
- `docx-extract-worker --consume` created `02_extract/text_units.json` from the converted DOCX.
- `translate-worker --consume` created `03_translate/translated_units.json`.
- `docx-replace-worker --consume` created `04_replace/translated.docx`.
- `libreoffice-worker --consume` copied translated DOCX to `05_export/final.docx` and wrote placeholder `05_export/final.pdf`.
- `libreoffice-worker --consume-marker` created `05_export/marker.docx`.
- `pdf2hwpx-worker --consume` created placeholder `06_hwpx/final.hwpx`.
- `email-worker` consumed `email_send`, called job-service sendability, wrote `reports/email_report.json`, and published `email_send stage.completed`.
- `job-service` consumed the email event and persisted `status=completed`, `current_stage=completed`.

Current limits:

- Static anchored `pdf2docx` is used, but the smoke sample remains the converter's local validation PDF.
- Downstream DOCX extraction/replacement still covers the MVP `word/document.xml` text-run path only.
- DOCX export still uses `DOCX_EXPORT_PDF_MODE=placeholder`.
- `pdf2hwpx` still writes a placeholder HWPX package containing `placeholder.json` and `source/marker.docx`.
- Email delivery remains mock-only.
- PostgreSQL persistence remains the JSONB aggregate smoke table; no outbox or normalized schema was added.

Next recommended step:

- HWPX, DOCX, and PDF route-level E2E coverage is now in place. The next step is operation/API/admin/replacement/closed-network documentation before Helm/local-stack, while real LibreOffice export, real `pdf2hwpx`, real HWPX `rhwp`, and real email provider integration remain separate implementation tracks.

## 2026-06-12 KST - Operation, API, admin, replacement, and closed-network docs

Done:

- Added `docs/USAGE.md` for user/frontend flows across PDF, DOCX, and HWPX jobs.
- Added `docs/API.md` to define `job-service` as the only public API entry point and to separate current implemented endpoints from target public endpoints.
- Added `docs/ADMIN_UI.md` with MVP admin UI requirements and the rule that admin UI must not publish RabbitMQ messages.
- Added `docs/INTEGRATION_GUIDE.md` for frontend/admin/system integration through `job-service`.
- Added `docs/REPLACEMENT_GUIDE.md` for `email-worker` provider replacement and `pdf2hwpx-worker` custom library replacement.
- Added `docs/CLOSED_NETWORK_DEPLOYMENT.md` for external RabbitMQ/MinIO/PostgreSQL requirements, queue initialization strategy, and closed-network image/config expectations.
- Updated `docs/CONTRACTS.md`, `docs/PIPELINE.md`, `docs/ARCHITECTURE.md`, and `docs/PROJECT_PLAN.md` to make the public API boundary explicit.
- Updated `docs/TROUBLESHOOTING.md` with frontend/admin RabbitMQ misuse, missing external queues, and upload-flow troubleshooting.
- Did not implement Helm charts.
- Did not implement admin UI, real military mail provider, real `pdf2hwpx`, or schema redesign.

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 96 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `scripts/dev/smoke-hwpx-route-e2e.sh`: passed.
- `scripts/dev/smoke-docx-route-e2e.sh`: passed.
- `scripts/dev/smoke-pdf-route-e2e.sh`: passed.

Current limits:

- The API document records target upload/download/retry/admin endpoints that are not fully implemented yet.
- Closed-network deployment notes define Helm requirements but Helm work remains pending.
- Email `smtp` and `military_api` providers remain documented replacement targets, not implemented providers.
- `pdf2hwpx` remains placeholder output until the closed-network custom library is available.

Next recommended step:

- Proceed to Helm/local-stack only after keeping the documented public boundary: frontend/admin/user clients call `job-service`, and RabbitMQ remains internal worker orchestration.

## 2026-06-12 KST - job-service API and Admin UI readiness

Done:

- Created branch `feat/admin-api-ui-readiness`.
- Added job-service public/admin APIs:
  - `GET /jobs/{job_id}/stages`
  - `GET /jobs/{job_id}/artifacts`
  - `POST /jobs/{job_id}/retry`
  - `GET /admin/jobs`
  - `GET /admin/jobs/{job_id}`
  - `GET /admin`
- Added admin list filtering by `status`, `input_type`, `current_stage`, and `user_id`.
- Added a minimal failed-job retry path mediated by `job-service`; non-failed jobs return `409 retry_not_allowed`.
- Added a lightweight Admin UI skeleton served by `job-service`; it calls only job-service APIs and does not use RabbitMQ/MinIO directly.
- Added `tests/test_job_service_api.py`.
- Added `scripts/dev/smoke-admin-api.sh`.
- Did not implement Helm charts.
- Did not change RabbitMQ into a frontend-facing interface.
- Did not add a large frontend framework.
- Did not change PostgreSQL schema.

Verified:

- `bash -n scripts/dev/smoke-admin-api.sh`: passed.
- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 100 tests.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `scripts/dev/check-env.sh`: passed with optional warnings for missing kind/native k3s.
- `scripts/dev/build-images.sh`: passed for all 9 images with tag `0.1.0`.
- `scripts/dev/smoke-images.sh`: passed for all 9 images.
- `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh`: passed.
- `scripts/dev/smoke-hwpx-route-e2e.sh`: passed.
- `scripts/dev/smoke-docx-route-e2e.sh`: passed.
- `scripts/dev/smoke-pdf-route-e2e.sh`: passed.

Current limits:

- Admin UI is a lightweight skeleton, not a full production console.
- Retry does not yet enforce MinIO artifact existence or attempt-limit policy.
- Download streaming/presigned download API remains pending.
- Helm/local-stack remains pending.

Next recommended step:

- Proceed to Helm/local-stack only after preserving the job-service-only public boundary.

## 2026-06-12 KST - Reliability, admin, and usage replan audit

Done:

- Created branch `docs/reliability-admin-usage-replan` from `feat/admin-api-ui-readiness`.
- Audited current RabbitMQ worker command consumption and confirmed workers ack command messages only after handler completion.
- Audited `job-service` orchestration and confirmed:
  - workers still do not publish next-stage commands
  - `job-service` consumes worker events and publishes next commands
  - cancellation gates exist
  - retry exists only for failed jobs
  - max attempts, backoff, stage lease, heartbeat, and idempotency keys are not implemented
- Audited `email-worker` sendability and confirmed terminal completed jobs are not sendable, but concurrent/duplicate `email_send` commands can still send twice before job-service records completion.
- Audited Admin API/UI and confirmed basic job/stage/artifact/error visibility exists, while lease/heartbeat/queue/timeline/attempt visibility is still missing.
- Added `docs/RELIABILITY_REPLAN.md`.
- Updated architecture, contracts, pipeline, API, Admin UI, usage, integration, replacement, closed-network, project plan, decisions, validation, and troubleshooting docs.
- Did not implement Helm charts.
- Did not change worker ack behavior.
- Did not change DB/repository behavior.
- Did not implement Admin UI features, Uptime Kuma automation, real military mail, or real custom `pdf2hwpx`.

Key finding:

- Current long-running workers couple RabbitMQ command ack to actual stage completion. For large inputs, this can leave commands unacked for the whole conversion/export and can cause redelivery/duplicate execution if the connection drops or heartbeats time out.

Recommended next implementation step:

- Implement `docs/RELIABILITY_REPLAN.md` Phase B/C/D before Helm:
  - job-service stage claim/lease/heartbeat
  - worker ack-after-claim flow
  - duplicate command/event no-op
  - bounded retry/backoff
  - duplicate email-send prevention

Verified:

- `python3 -m compileall -q services tests`: passed.
- `python3 -m unittest discover -s tests`: passed, 100 tests.
- `git diff --check`: passed.
- `PYTHON_BIN=python3 scripts/dev/smoke-services.sh`: passed for all 9 services.
- `PYTHON_BIN=python3 scripts/dev/smoke-hwpx-local.sh`: passed.
- `PYTHON_BIN=python3 scripts/dev/smoke-admin-api.sh`: passed.
