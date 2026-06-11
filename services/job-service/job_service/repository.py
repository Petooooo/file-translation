"""Job repository implementations for local and live orchestration smoke tests."""

from __future__ import annotations

import json
from threading import RLock

from ft_common.config import AppConfig
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

    def save(self, job: Job) -> Job:
        return self.add(job)

    def get(self, job_id: str) -> Job:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


class PostgresJobRepository:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: str,
    ) -> None:
        self.connection_kwargs = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
        }
        self._ensure_schema()

    @classmethod
    def from_config(cls, config: AppConfig) -> "PostgresJobRepository":
        return cls(
            host=config.postgres_host,
            port=config.postgres_port,
            dbname=config.postgres_db,
            user=config.postgres_user,
            password=config.postgres_password,
        )

    def add(self, job: Job) -> Job:
        return self.save(job)

    def save(self, job: Job) -> Job:
        payload = json.dumps(job.to_dict(), separators=(",", ":"), sort_keys=True)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (job_id, payload, updated_at)
                    VALUES (%s, %s::jsonb, now())
                    ON CONFLICT (job_id)
                    DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (job.job_id, payload),
                )
        return job

    def get(self, job_id: str) -> Job:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
        if row is None:
            raise JobNotFoundError(job_id)
        return _job_from_payload(row[0])

    def list(self) -> list[Job]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs ORDER BY job_id")
                rows = cursor.fetchall()
        return [_job_from_payload(row[0]) for row in rows]

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id text PRIMARY KEY,
                        payload jsonb NOT NULL,
                        updated_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )

    def _connect(self):
        try:
            import psycopg  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL repository mode requires the optional 'psycopg' package"
            ) from exc
        return psycopg.connect(**self.connection_kwargs)


def _job_from_payload(payload: object) -> Job:
    if isinstance(payload, str):
        decoded = json.loads(payload)
    else:
        decoded = payload
    if not isinstance(decoded, dict):
        raise ValueError("jobs.payload must contain a JSON object")
    return Job.from_dict(decoded)
