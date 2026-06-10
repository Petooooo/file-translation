"""Thread-safe in-memory repository until PostgreSQL is added."""

from __future__ import annotations

from threading import RLock

from job_service.models import Job


class JobNotFoundError(KeyError):
    pass


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = RLock()

    def add(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.job_id] = job
            return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())
