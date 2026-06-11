# Phase 2 Skeleton Services Plan

Last updated: 2026-06-10 01:16 KST

## Objective

Create minimal service skeletons for:

- `job-service`
- `pdf2docx-worker`
- `docx-extract-worker`
- `translate-worker`
- `docx-replace-worker`
- `libreoffice-worker`
- `pdf2hwpx-worker`
- `email-worker`

This phase does not implement RabbitMQ orchestration, MinIO artifact transfer, PostgreSQL persistence, or document conversion logic. Those remain Phase 3 and later.

## Runtime Choice

Use Python 3.12 and the standard library for the first skeleton.

Reason:

- Keeps local validation fast and independent of package registries.
- Avoids paid keys and external service dependencies.
- Gives every service a runnable Docker image immediately.
- Can evolve to FastAPI, aio-pika, SQLAlchemy, and MinIO SDK in later phases when the integration surface is clearer.

## Planned Repository Layout

```text
services/
  common/ft_common/
    config.py
    health.py
    logging.py
    object_keys.py
    service.py
  job-service/
    Dockerfile
    app.py
  pdf2docx-worker/
    Dockerfile
    worker.py
  docx-extract-worker/
    Dockerfile
    worker.py
  translate-worker/
    Dockerfile
    worker.py
  docx-replace-worker/
    Dockerfile
    worker.py
  libreoffice-worker/
    Dockerfile
    worker.py
  pdf2hwpx-worker/
    Dockerfile
    worker.py
  email-worker/
    Dockerfile
    worker.py
tests/
  test_config.py
  test_object_keys.py
  test_service_smoke.py
```

## Skeleton Behavior

`job-service`:

- starts a tiny HTTP server using Python stdlib
- exposes `/healthz`, `/readyz`, and `/config`
- reads config from environment
- logs structured JSON lines
- returns no secrets in HTTP responses

Workers:

- run a smoke command by default during tests
- can run a long-lived idle loop for container execution
- read stage queue names and shared infrastructure settings from environment
- log startup configuration without secrets
- do not publish next-stage commands
- do not touch PostgreSQL or MinIO yet

## Configuration Baseline

Use environment variables only. Defaults are local-development friendly and match the architecture docs:

- `APP_ENV=local`
- `NAMESPACE=file-translation`
- `RABBITMQ_HOST=rabbitmq`
- `RABBITMQ_PORT=5672`
- `RABBITMQ_VHOST=/`
- `MINIO_ENDPOINT=http://minio:9000`
- `MINIO_BUCKET=file-translation`
- `POSTGRES_HOST=postgresql`
- `POSTGRES_PORT=5432`
- `POSTGRES_DB=file_translation`
- `TRANSLATION_PROVIDER=mock`
- `TRANSLATION_API_BASE_URL=http://translation-api`
- command queue env vars for all stages
- event queue env vars for stage completion, failure, and progress

Sensitive values are intentionally not required in Phase 2.

## Validation Plan

Run:

```bash
python3 -m unittest discover -s tests
python3 services/job-service/app.py --smoke
python3 services/pdf2docx-worker/worker.py --smoke
python3 services/docx-extract-worker/worker.py --smoke
python3 services/translate-worker/worker.py --smoke
python3 services/docx-replace-worker/worker.py --smoke
python3 services/libreoffice-worker/worker.py --smoke
python3 services/pdf2hwpx-worker/worker.py --smoke
python3 services/email-worker/worker.py --smoke
docker build -t petoo/file-translation-job-service:0.1.0 -f services/job-service/Dockerfile .
```

Build every worker image if Docker build time is acceptable. Do not push images in Phase 2 unless all image builds and smoke tests pass and Docker Hub login is already available.

## Completion Criteria

- all skeleton services exist
- every service has a Dockerfile
- every service has a smoke command
- job-service has a health HTTP endpoint
- shared config and logging are covered by unit tests
- MinIO object key convention has a pure function and unit tests
- docs record commands run and known gaps

## Result

Completed on branch `codex/feat-skeleton-services`.

## Replan Note

The skeleton remains useful, but later branches must align worker stage names and queue defaults with `docs/PIPELINE.md` and `docs/CONTRACTS.md`.
