"""job-service client used by email-worker sendability checks."""

from __future__ import annotations

import json
from typing import Protocol
from urllib import request
from urllib.parse import quote

from ft_common.config import AppConfig


class JobServiceClient(Protocol):
    def get_sendability(self, job_id: str) -> dict[str, object]:
        ...


class HttpJobServiceClient:
    def __init__(self, *, base_url: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, config: AppConfig) -> "HttpJobServiceClient":
        return cls(
            base_url=config.job_service_url,
            timeout_seconds=config.email_api_timeout_seconds,
        )

    def get_sendability(self, job_id: str) -> dict[str, object]:
        url = f"{self.base_url}/jobs/{quote(job_id, safe='')}/sendability"
        with request.urlopen(url, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("job-service sendability response must be a JSON object")
        return payload
