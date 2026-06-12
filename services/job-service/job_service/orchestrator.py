"""job-service input routing and event orchestration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from ft_common.object_keys import artifact_key, job_prefix
from job_service.models import Job, StageState, utc_now
from job_service.publisher import CommandEnvelope, CommandPublisher
from job_service.routes import initial_stage, next_stage, pipeline_route, validate_input_type


class JobRetryNotAllowedError(ValueError):
    pass


class JobService:
    def __init__(
        self,
        repository: object,
        publisher: CommandPublisher,
        *,
        lease_seconds: int = 300,
        heartbeat_interval_seconds: int = 30,
        max_attempts: int = 3,
    ) -> None:
        self.repository = repository
        self.publisher = publisher
        self.lease_seconds = lease_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.max_attempts = max_attempts

    def create_job(
        self,
        *,
        user_id: str,
        input_type: str,
        source_lang: str,
        target_lang: str,
        original_filename: str,
        file_id: str | None = None,
        job_id: str | None = None,
        input_object_key: str | None = None,
        today: date | None = None,
    ) -> tuple[Job, CommandEnvelope]:
        normalized_input_type = validate_input_type(input_type)
        resolved_today = today or date.today()
        resolved_file_id = file_id or uuid4().hex[:12]
        resolved_job_id = job_id or str(uuid4())
        route = pipeline_route(normalized_input_type)
        first_stage = initial_stage(normalized_input_type)
        prefix = job_prefix(resolved_today, user_id, resolved_file_id)
        input_key = input_object_key or artifact_key(
            resolved_today,
            user_id,
            resolved_file_id,
            f"input/original.{normalized_input_type}",
        )

        stages = {"receive_input": StageState("receive_input", status="completed", completed_at=utc_now())}
        for stage in route:
            stages[stage] = StageState(stage, max_attempts=self.max_attempts)
        stages[first_stage].status = "running"
        stages[first_stage].attempts = 1
        stages[first_stage].started_at = utc_now()

        job = Job(
            job_id=resolved_job_id,
            user_id=user_id,
            file_id=resolved_file_id,
            input_type=normalized_input_type,
            source_lang=source_lang,
            target_lang=target_lang,
            status="running",
            current_stage=first_stage,
            pipeline_route=route,
            object_prefix=prefix,
            original_filename=original_filename,
            input_object_key=input_key,
            stages=stages,
            artifacts={"input": input_key},
        )
        self.repository.add(job)
        command = self.publisher.publish_command(job, first_stage)
        return job, command

    def get_job(self, job_id: str) -> Job:
        return self.repository.get(job_id)

    def list_jobs(self, filters: dict[str, str] | None = None) -> list[Job]:
        jobs = list(self.repository.list())
        filters = filters or {}
        for field in ("status", "input_type", "current_stage", "user_id"):
            expected = filters.get(field)
            if expected:
                jobs = [job for job in jobs if str(getattr(job, field)) == expected]
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def job_summary(self, job: Job) -> dict[str, object]:
        return {
            "job_id": job.job_id,
            "user_id": job.user_id,
            "file_id": job.file_id,
            "input_type": job.input_type,
            "status": job.status,
            "current_stage": job.current_stage,
            "original_filename": job.original_filename,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_stage": job.error_stage,
            "error_message": job.error_message,
        }

    def stages_payload(self, job_id: str) -> dict[str, object]:
        job = self.repository.get(job_id)
        ordered_names = ["receive_input", *job.pipeline_route]
        seen: set[str] = set()
        stages: list[dict[str, object]] = []
        for stage in ordered_names:
            state = job.stages.get(stage)
            if state is not None:
                stages.append(state.to_dict())
                seen.add(stage)
        for stage, state in job.stages.items():
            if stage not in seen:
                stages.append(state.to_dict())
        return {"job_id": job.job_id, "stages": stages}

    def artifacts_payload(self, job_id: str) -> dict[str, object]:
        job = self.repository.get(job_id)
        artifacts = _artifact_items(job)
        return {"job_id": job.job_id, "object_prefix": job.object_prefix, "artifacts": artifacts}

    def cancel_job(self, job_id: str) -> Job:
        job = self.repository.get(job_id)
        if job.status == "completed":
            return job
        now = utc_now()
        job.status = "cancel_requested"
        job.cancel_requested_at = now
        job.updated_at = now
        self.repository.save(job)
        return job

    def retry_job(self, job_id: str, stage: str | None = None) -> tuple[Job, CommandEnvelope]:
        job = self.repository.get(job_id)
        retry_stage = stage or job.error_stage
        if job.status != "failed":
            raise JobRetryNotAllowedError(f"job status={job.status} is not retryable")
        if retry_stage is None:
            raise JobRetryNotAllowedError("failed job has no retry stage")
        if retry_stage not in job.pipeline_route:
            raise JobRetryNotAllowedError(f"stage {retry_stage!r} is not in the job route")

        now = utc_now()
        retry_index = job.pipeline_route.index(retry_stage)
        retry_state = job.stages.setdefault(retry_stage, StageState(retry_stage))
        retry_state.max_attempts = retry_state.max_attempts or self.max_attempts
        if retry_state.attempts >= retry_state.max_attempts:
            raise JobRetryNotAllowedError(
                f"stage {retry_stage!r} exceeded max_attempts={retry_state.max_attempts}"
            )
        retry_state.status = "running"
        retry_state.attempts += 1
        retry_state.started_at = now
        retry_state.completed_at = None
        retry_state.error_message = None
        retry_state.last_error = None
        retry_state.retryable = None
        retry_state.command_id = None
        retry_state.claim_id = None
        retry_state.idempotency_key = None
        retry_state.claimed_by = None
        retry_state.lease_until = None
        retry_state.last_heartbeat_at = None
        retry_state.progress = 0
        retry_state.lease_expired = False
        retry_state.reconciled_at = None
        retry_state.retry_backoff_seconds = 0
        retry_state.next_retry_at = None
        retry_state.last_reconcile_reason = None

        for downstream_stage in job.pipeline_route[retry_index + 1 :]:
            state = job.stages.setdefault(downstream_stage, StageState(downstream_stage))
            if state.status != "completed":
                state.status = "pending"
                state.started_at = None
                state.completed_at = None
                state.error_message = None
                state.last_error = None
                state.retryable = None
                state.command_id = None
                state.claim_id = None
                state.idempotency_key = None
                state.claimed_by = None
                state.lease_until = None
                state.last_heartbeat_at = None
                state.progress = 0
                state.lease_expired = False
                state.reconciled_at = None
                state.retry_backoff_seconds = 0
                state.next_retry_at = None
                state.last_reconcile_reason = None
                state.stale_attempts = 0

        job.status = "running"
        job.current_stage = retry_stage
        job.error_stage = None
        job.error_message = None
        job.completed_at = None
        job.updated_at = now
        self.repository.save(job)
        command = self.publisher.publish_command(job, retry_stage)
        return job, command

    def claim_stage(
        self,
        job_id: str,
        stage: str,
        *,
        command_id: str | None = None,
        attempt: int | None = None,
        worker_id: str | None = None,
        idempotency_key: str | None = None,
        lease_seconds: int | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, object]:
        resolved_stage = str(stage)

        def mutate(job: Job) -> dict[str, object]:
            return self._claim_stage_on_job(
                job,
                resolved_stage,
                command_id=command_id,
                attempt=attempt,
                worker_id=worker_id,
                idempotency_key=idempotency_key,
                lease_seconds=lease_seconds,
                max_attempts=max_attempts,
            )

        return self.repository.mutate(job_id, mutate)

    def heartbeat_stage(
        self,
        job_id: str,
        stage: str,
        *,
        claim_id: str | None = None,
        progress: float | None = None,
        lease_seconds: int | None = None,
    ) -> dict[str, object]:
        resolved_stage = str(stage)

        def mutate(job: Job) -> dict[str, object]:
            now = utc_now()
            state = job.stages.get(resolved_stage)
            if state is None or resolved_stage not in job.pipeline_route:
                return _claim_payload("INVALID_STAGE", job, StageState(resolved_stage), should_process=False)
            if claim_id and state.claim_id and claim_id != state.claim_id:
                return _claim_payload("INVALID_STAGE", job, state, should_process=False, reason="claim_id mismatch")
            state.last_heartbeat_at = now
            state.lease_until = now + timedelta(seconds=lease_seconds or self.lease_seconds)
            if progress is not None:
                state.progress = _bounded_progress(progress)
            job.updated_at = now
            return _claim_payload("CLAIMED", job, state, should_process=True)

        return self.repository.mutate(job_id, mutate)

    def reconcile_stale_leases(self, *, retry_backoff_seconds: int = 0) -> dict[str, object]:
        now = utc_now()
        actions_payload: list[dict[str, object]] = []
        published_payload: list[dict[str, object]] = []
        result: dict[str, object] = {
            "status": "reconciled",
            "reconciled_at": now.isoformat(),
            "scanned_jobs": 0,
            "stale_stages": 0,
            "retried": 0,
            "failed": 0,
            "cancelled": 0,
            "noop": 0,
            "actions": actions_payload,
            "published_commands": published_payload,
        }
        job_ids = [job.job_id for job in self.repository.list()]
        result["scanned_jobs"] = len(job_ids)

        for job_id in job_ids:
            actions = self.repository.mutate(
                job_id,
                lambda job, now=now: self._reconcile_stale_leases_on_job(
                    job,
                    now=now,
                    retry_backoff_seconds=retry_backoff_seconds,
                ),
            )
            for action in actions:
                actions_payload.append(action)
                result["stale_stages"] = int(result["stale_stages"]) + 1
                action_name = str(action["action"])
                if action_name == "retry":
                    job = self.repository.get(str(action["job_id"]))
                    command = self.publisher.publish_command(job, str(action["stage"]))
                    published_payload.append({"queue": command.queue, "message": command.message})
                    result["retried"] = int(result["retried"]) + 1
                elif action_name == "failed":
                    result["failed"] = int(result["failed"]) + 1
                elif action_name == "cancelled":
                    result["cancelled"] = int(result["cancelled"]) + 1
                else:
                    result["noop"] = int(result["noop"]) + 1

        return result

    def sendability(self, job_id: str) -> dict[str, object]:
        job = self.repository.get(job_id)
        sendable = job.status == "running" and job.current_stage == "email_send"
        reason = None
        if not sendable:
            reason = f"job status={job.status} current_stage={job.current_stage} is not sendable"
        artifacts = dict(job.artifacts)
        if job.final_docx_key:
            artifacts["final_docx"] = job.final_docx_key
        if job.final_pdf_key:
            artifacts["final_pdf"] = job.final_pdf_key
        if job.final_hwpx_key:
            artifacts["final_hwpx"] = job.final_hwpx_key
        if job.translated_hwpx_key:
            artifacts["translated_hwpx"] = job.translated_hwpx_key
        return {
            "job_id": job.job_id,
            "sendable": sendable,
            "status": job.status,
            "current_stage": job.current_stage,
            "reason": reason,
            "input_type": job.input_type,
            "user_id": job.user_id,
            "file_id": job.file_id,
            "source_lang": job.source_lang,
            "target_lang": job.target_lang,
            "object_prefix": job.object_prefix,
            "original_filename": job.original_filename,
            "artifacts": artifacts,
        }

    def handle_event(self, event: dict[str, object]) -> CommandEnvelope | None:
        event_type = str(event.get("event_type", ""))
        if event_type == "stage.completed":
            return self._handle_stage_completed(event)
        if event_type == "stage.failed":
            self._handle_stage_failed(event)
            return None
        if event_type.endswith(".progress") or event_type == "progress":
            self._handle_progress(event)
            return None
        raise ValueError(f"unsupported event_type: {event_type!r}")

    def _handle_stage_completed(self, event: dict[str, object]) -> CommandEnvelope | None:
        job = self.repository.get(str(event["job_id"]))
        stage = str(event["stage"])
        now = utc_now()

        if job.is_cancel_blocked():
            job.status = "cancelled"
            job.current_stage = "cancelled"
            job.completed_at = now
            job.updated_at = now
            self.repository.save(job)
            return None
        if job.is_terminal():
            return None

        state = job.stages.setdefault(stage, StageState(stage))
        if state.status == "completed":
            return None
        if stage not in job.pipeline_route or job.current_stage != stage:
            return None
        if _is_stale_event(event, state):
            return None
        state.status = "completed"
        state.completed_at = now
        state.last_heartbeat_at = now
        state.progress = 100
        state.retryable = None
        state.last_error = None
        state.lease_expired = False
        outputs = event.get("outputs")
        if isinstance(outputs, dict):
            state.outputs.update({str(key): str(value) for key, value in outputs.items()})
            job.artifacts.update({str(key): str(value) for key, value in outputs.items()})
            self._update_final_keys(job)

        following_stage = next_stage(job.pipeline_route, stage)
        if following_stage is None:
            job.status = "completed"
            job.current_stage = "completed"
            job.completed_at = now
            job.updated_at = now
            self.repository.save(job)
            return None

        next_state = job.stages.setdefault(following_stage, StageState(following_stage))
        next_state.status = "running"
        next_state.attempts += 1
        next_state.started_at = now
        next_state.completed_at = None
        next_state.error_message = None
        next_state.last_error = None
        next_state.retryable = None
        next_state.command_id = None
        next_state.claim_id = None
        next_state.idempotency_key = None
        next_state.claimed_by = None
        next_state.lease_until = None
        next_state.last_heartbeat_at = None
        next_state.max_attempts = next_state.max_attempts or self.max_attempts
        next_state.progress = 0
        next_state.lease_expired = False
        next_state.reconciled_at = None
        next_state.retry_backoff_seconds = 0
        next_state.next_retry_at = None
        next_state.last_reconcile_reason = None
        next_state.stale_attempts = 0
        job.status = "running"
        job.current_stage = following_stage
        job.updated_at = now
        self.repository.save(job)
        return self.publisher.publish_command(job, following_stage)

    def _handle_stage_failed(self, event: dict[str, object]) -> None:
        job = self.repository.get(str(event["job_id"]))
        stage = str(event["stage"])
        now = utc_now()
        error_message = str(event.get("error_message", "stage failed"))

        if job.is_terminal():
            return
        state = job.stages.setdefault(stage, StageState(stage))
        if stage not in job.pipeline_route or job.current_stage != stage:
            return
        if state.status == "completed" or _is_stale_event(event, state):
            return
        state.status = "failed"
        state.error_message = error_message
        state.completed_at = now
        state.last_heartbeat_at = now
        state.last_error = error_message
        state.retryable = bool(event.get("retryable", False))
        state.lease_expired = False

        job.status = "failed"
        job.current_stage = "failed"
        job.error_stage = stage
        job.error_message = error_message
        job.completed_at = now
        job.updated_at = now
        self.repository.save(job)

    def _handle_progress(self, event: dict[str, object]) -> None:
        job = self.repository.get(str(event["job_id"]))
        stage = str(event.get("stage", ""))
        state = job.stages.get(stage)
        if state is not None:
            state.last_heartbeat_at = utc_now()
            if "progress" in event:
                state.progress = _bounded_progress(event["progress"])
        job.progress = {
            key: value
            for key, value in event.items()
            if key in {"event_type", "stage", "total_units", "translated_units", "failed_units", "progress"}
        }
        job.updated_at = utc_now()
        self.repository.save(job)

    def _claim_stage_on_job(
        self,
        job: Job,
        stage: str,
        *,
        command_id: str | None,
        attempt: int | None,
        worker_id: str | None,
        idempotency_key: str | None,
        lease_seconds: int | None,
        max_attempts: int | None,
    ) -> dict[str, object]:
        now = utc_now()
        state = job.stages.setdefault(stage, StageState(stage, max_attempts=max_attempts or self.max_attempts))
        state.max_attempts = max_attempts or state.max_attempts or self.max_attempts

        if stage not in job.pipeline_route:
            return _claim_payload("INVALID_STAGE", job, state, should_process=False, reason="stage is not in route")
        if job.status in {"cancel_requested", "cancelled"}:
            return _claim_payload("JOB_CANCELLED", job, state, should_process=False)
        if state.status == "completed" or job.status == "completed":
            return _claim_payload("ALREADY_COMPLETED", job, state, should_process=False)
        if job.is_terminal():
            return _claim_payload("JOB_CANCELLED", job, state, should_process=False)
        if job.current_stage != stage:
            return _claim_payload("INVALID_STAGE", job, state, should_process=False, reason="stage is not current")

        requested_attempt = attempt or state.attempts or 1
        if requested_attempt > state.max_attempts:
            state.status = "failed"
            state.error_message = f"max_attempts={state.max_attempts} exceeded"
            state.last_error = state.error_message
            state.completed_at = now
            state.retryable = False
            job.status = "failed"
            job.current_stage = "failed"
            job.error_stage = stage
            job.error_message = state.error_message
            job.completed_at = now
            job.updated_at = now
            return _claim_payload("MAX_ATTEMPTS_EXCEEDED", job, state, should_process=False)

        lease_alive = state.lease_until is not None and state.lease_until > now
        if state.status == "running" and state.command_id and lease_alive:
            return _claim_payload("ALREADY_RUNNING", job, state, should_process=False)
        if stage == "email_send" and state.status == "running" and state.command_id:
            return _claim_payload("ALREADY_RUNNING", job, state, should_process=False)
        if state.status == "running" and state.command_id and requested_attempt <= state.attempts:
            return _claim_payload("ALREADY_RUNNING", job, state, should_process=False)
        if state.attempts >= state.max_attempts and requested_attempt > state.attempts:
            state.status = "failed"
            state.error_message = f"max_attempts={state.max_attempts} exceeded"
            state.last_error = state.error_message
            state.completed_at = now
            state.retryable = False
            job.status = "failed"
            job.current_stage = "failed"
            job.error_stage = stage
            job.error_message = state.error_message
            job.completed_at = now
            job.updated_at = now
            return _claim_payload("MAX_ATTEMPTS_EXCEEDED", job, state, should_process=False)

        resolved_command_id = command_id or f"{job.job_id}:{stage}:{requested_attempt}"
        state.status = "running"
        state.attempts = max(state.attempts, requested_attempt)
        state.command_id = resolved_command_id
        state.claim_id = resolved_command_id
        state.idempotency_key = idempotency_key or resolved_command_id
        state.claimed_by = worker_id
        state.started_at = state.started_at or now
        state.completed_at = None
        state.lease_until = now + timedelta(seconds=lease_seconds or self.lease_seconds)
        state.last_heartbeat_at = now
        state.progress = 0 if state.progress >= 100 else state.progress
        state.long_running = True
        state.lease_expired = False
        state.next_retry_at = None
        state.error_message = None
        state.last_error = None
        state.retryable = None
        job.status = "running"
        job.current_stage = stage
        job.updated_at = now
        return _claim_payload("CLAIMED", job, state, should_process=True)

    def _reconcile_stale_leases_on_job(
        self,
        job: Job,
        *,
        now: datetime,
        retry_backoff_seconds: int,
    ) -> list[dict[str, object]]:
        if job.is_terminal():
            return []

        actions: list[dict[str, object]] = []
        for stage in job.pipeline_route:
            state = job.stages.get(stage)
            if state is None or state.status != "running" or state.lease_until is None:
                continue
            if state.lease_until > now:
                continue
            if job.current_stage != stage:
                state.lease_expired = True
                state.reconciled_at = now
                state.last_reconcile_reason = "stale_non_current_stage_ignored"
                actions.append(_reconcile_action("noop", job, state, "stale_non_current_stage_ignored", now))
                continue

            action = self._reconcile_current_stale_stage(
                job,
                state,
                now=now,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            actions.append(action)
            break

        if actions:
            job.updated_at = now
        return actions

    def _reconcile_current_stale_stage(
        self,
        job: Job,
        state: StageState,
        *,
        now: datetime,
        retry_backoff_seconds: int,
    ) -> dict[str, object]:
        previous_attempt = state.attempts
        reason = "stale_lease_expired"
        state.stale_attempts += 1
        state.reconciled_at = now
        state.retry_backoff_seconds = max(0, int(retry_backoff_seconds))

        if job.status in {"cancel_requested", "cancelled"}:
            state.status = "cancelled"
            state.completed_at = now
            state.lease_expired = True
            state.retryable = False
            state.last_reconcile_reason = "job_cancelled_no_retry"
            state.last_error = "job was cancelled while the stage lease was stale"
            job.status = "cancelled"
            job.current_stage = "cancelled"
            job.completed_at = now
            return _reconcile_action("cancelled", job, state, state.last_reconcile_reason, now, previous_attempt)

        if state.stage == "email_send":
            error = "email_send lease expired; automatic retry is disabled to prevent duplicate sends"
            state.status = "failed"
            state.error_message = error
            state.last_error = error
            state.completed_at = now
            state.lease_expired = True
            state.retryable = False
            state.last_reconcile_reason = "email_send_stale_no_auto_retry"
            job.status = "failed"
            job.current_stage = "failed"
            job.error_stage = state.stage
            job.error_message = error
            job.completed_at = now
            return _reconcile_action("failed", job, state, state.last_reconcile_reason, now, previous_attempt)

        if state.attempts >= state.max_attempts:
            error = f"stale lease expired and max_attempts={state.max_attempts} exhausted"
            state.status = "failed"
            state.error_message = error
            state.last_error = error
            state.completed_at = now
            state.lease_expired = True
            state.retryable = False
            state.last_reconcile_reason = "max_attempts_exceeded"
            job.status = "failed"
            job.current_stage = "failed"
            job.error_stage = state.stage
            job.error_message = error
            job.completed_at = now
            return _reconcile_action("failed", job, state, state.last_reconcile_reason, now, previous_attempt)

        state.attempts += 1
        state.status = "running"
        state.started_at = now
        state.completed_at = None
        state.command_id = None
        state.claim_id = None
        state.idempotency_key = None
        state.claimed_by = None
        state.lease_until = None
        state.last_heartbeat_at = None
        state.progress = 0
        state.long_running = True
        state.retryable = None
        state.error_message = None
        state.last_error = None
        state.lease_expired = False
        state.next_retry_at = now
        state.last_reconcile_reason = reason
        job.status = "running"
        job.current_stage = state.stage
        job.error_stage = None
        job.error_message = None
        job.completed_at = None
        return _reconcile_action("retry", job, state, reason, now, previous_attempt)

    def _update_final_keys(self, job: Job) -> None:
        if "final_docx" in job.artifacts:
            job.final_docx_key = job.artifacts["final_docx"]
        if "final_pdf" in job.artifacts:
            job.final_pdf_key = job.artifacts["final_pdf"]
        if "final_hwpx" in job.artifacts:
            job.final_hwpx_key = job.artifacts["final_hwpx"]
        if "translated_hwpx" in job.artifacts:
            job.translated_hwpx_key = job.artifacts["translated_hwpx"]


def _artifact_items(job: Job) -> list[dict[str, object]]:
    values = dict(job.artifacts)
    if job.final_docx_key:
        values["final_docx"] = job.final_docx_key
    if job.final_pdf_key:
        values["final_pdf"] = job.final_pdf_key
    if job.final_hwpx_key:
        values["final_hwpx"] = job.final_hwpx_key
    if job.translated_hwpx_key:
        values["translated_hwpx"] = job.translated_hwpx_key

    artifacts: list[dict[str, object]] = []
    for artifact_type, object_key in sorted(values.items()):
        artifacts.append(
            {
                "artifact_type": artifact_type,
                "object_key": object_key,
                "content_type": None,
                "size": None,
                "created_at": None,
                "download_available": True,
            }
        )
    return artifacts


def _claim_payload(
    claim_status: str,
    job: Job,
    state: StageState,
    *,
    should_process: bool,
    reason: str | None = None,
) -> dict[str, object]:
    return {
        "status": claim_status.lower(),
        "claim_status": claim_status,
        "should_process": should_process,
        "reason": reason,
        "job_id": job.job_id,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "stage": state.stage,
        "attempt": state.attempts,
        "max_attempts": state.max_attempts,
        "command_id": state.command_id,
        "claim_id": state.claim_id,
        "idempotency_key": state.idempotency_key,
        "lease_until": state.lease_until.isoformat() if state.lease_until else None,
        "last_heartbeat_at": state.last_heartbeat_at.isoformat() if state.last_heartbeat_at else None,
        "progress": state.progress,
        "lease_expired": state.lease_expired,
        "reconciled_at": state.reconciled_at.isoformat() if state.reconciled_at else None,
        "retry_count": max(state.attempts - 1, 0),
        "retry_backoff_seconds": state.retry_backoff_seconds,
        "next_retry_at": state.next_retry_at.isoformat() if state.next_retry_at else None,
        "last_reconcile_reason": state.last_reconcile_reason,
        "stale_attempts": state.stale_attempts,
    }


def _reconcile_action(
    action: str,
    job: Job,
    state: StageState,
    reason: str,
    now: datetime,
    previous_attempt: int | None = None,
) -> dict[str, object]:
    return {
        "action": action,
        "job_id": job.job_id,
        "stage": state.stage,
        "status": state.status,
        "job_status": job.status,
        "current_stage": job.current_stage,
        "reason": reason,
        "attempt": state.attempts,
        "previous_attempt": previous_attempt if previous_attempt is not None else state.attempts,
        "max_attempts": state.max_attempts,
        "retry_count": max(state.attempts - 1, 0),
        "stale_attempts": state.stale_attempts,
        "next_retry_at": state.next_retry_at.isoformat() if state.next_retry_at else None,
        "reconciled_at": now.isoformat(),
    }


def _is_stale_event(event: dict[str, object], state: StageState) -> bool:
    event_claim_id = _optional_str(event.get("claim_id"))
    if event_claim_id and state.claim_id and event_claim_id != state.claim_id:
        return True
    event_command_id = _optional_str(event.get("command_id"))
    if event_command_id and state.command_id and event_command_id != state.command_id:
        return True
    event_attempt = event.get("attempt")
    if event_attempt is not None:
        try:
            if int(event_attempt) != state.attempts:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _bounded_progress(value: object) -> float:
    try:
        progress = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(progress, 100))
