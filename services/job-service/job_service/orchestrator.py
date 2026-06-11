"""job-service input routing and event orchestration."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from ft_common.object_keys import artifact_key, job_prefix
from job_service.models import Job, StageState, utc_now
from job_service.publisher import CommandEnvelope, CommandPublisher
from job_service.repository import InMemoryJobRepository
from job_service.routes import initial_stage, next_stage, pipeline_route, validate_input_type


class JobService:
    def __init__(self, repository: InMemoryJobRepository, publisher: CommandPublisher) -> None:
        self.repository = repository
        self.publisher = publisher

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
            stages[stage] = StageState(stage)
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

    def cancel_job(self, job_id: str) -> Job:
        job = self.repository.get(job_id)
        if job.status == "completed":
            return job
        now = utc_now()
        job.status = "cancel_requested"
        job.cancel_requested_at = now
        job.updated_at = now
        return job

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
            return None
        if job.is_terminal():
            return None

        state = job.stages.setdefault(stage, StageState(stage))
        state.status = "completed"
        state.completed_at = now
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
            return None

        next_state = job.stages.setdefault(following_stage, StageState(following_stage))
        next_state.status = "running"
        next_state.attempts += 1
        next_state.started_at = now
        job.status = "running"
        job.current_stage = following_stage
        job.updated_at = now
        return self.publisher.publish_command(job, following_stage)

    def _handle_stage_failed(self, event: dict[str, object]) -> None:
        job = self.repository.get(str(event["job_id"]))
        stage = str(event["stage"])
        now = utc_now()
        error_message = str(event.get("error_message", "stage failed"))

        state = job.stages.setdefault(stage, StageState(stage))
        state.status = "failed"
        state.error_message = error_message
        state.completed_at = now

        job.status = "failed"
        job.current_stage = "failed"
        job.error_stage = stage
        job.error_message = error_message
        job.completed_at = now
        job.updated_at = now

    def _handle_progress(self, event: dict[str, object]) -> None:
        job = self.repository.get(str(event["job_id"]))
        job.progress = {
            key: value
            for key, value in event.items()
            if key in {"event_type", "stage", "total_units", "translated_units", "failed_units"}
        }
        job.updated_at = utc_now()

    def _update_final_keys(self, job: Job) -> None:
        if "final_docx" in job.artifacts:
            job.final_docx_key = job.artifacts["final_docx"]
        if "final_pdf" in job.artifacts:
            job.final_pdf_key = job.artifacts["final_pdf"]
        if "final_hwpx" in job.artifacts:
            job.final_hwpx_key = job.artifacts["final_hwpx"]
        if "translated_hwpx" in job.artifacts:
            job.translated_hwpx_key = job.artifacts["translated_hwpx"]
