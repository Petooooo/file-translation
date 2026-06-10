"""MinIO artifact store helpers used by workers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from ft_common.config import AppConfig


class ArtifactStore(Protocol):
    def download_file(self, object_key: str, destination: Path) -> None:
        ...

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        ...


@dataclass(frozen=True)
class MinioConnectionSettings:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    secure: bool

    @classmethod
    def from_config(cls, config: AppConfig) -> "MinioConnectionSettings":
        endpoint, secure = normalize_minio_endpoint(config.minio_endpoint)
        return cls(
            endpoint=endpoint,
            bucket=config.minio_bucket,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=secure,
        )


class MinioArtifactStore:
    def __init__(self, settings: MinioConnectionSettings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or build_minio_client(settings)

    @classmethod
    def from_config(cls, config: AppConfig) -> "MinioArtifactStore":
        return cls(MinioConnectionSettings.from_config(config))

    def download_file(self, object_key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.fget_object(self.settings.bucket, object_key, str(destination))

    def upload_file(self, object_key: str, source: Path, content_type: str | None = None) -> None:
        kwargs: dict[str, object] = {}
        if content_type is not None:
            kwargs["content_type"] = content_type
        self.client.fput_object(self.settings.bucket, object_key, str(source), **kwargs)


def normalize_minio_endpoint(endpoint: str) -> tuple[str, bool]:
    parsed = urlparse(endpoint)
    if parsed.scheme in {"http", "https"}:
        if not parsed.netloc:
            raise ValueError(f"invalid MinIO endpoint: {endpoint!r}")
        return parsed.netloc, parsed.scheme == "https"
    return endpoint, False


def build_minio_client(settings: MinioConnectionSettings) -> Any:
    if not settings.access_key or not settings.secret_key:
        raise RuntimeError("MinIO mode requires MINIO_ACCESS_KEY and MINIO_SECRET_KEY")
    try:
        from minio import Minio  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("MinIO artifact mode requires the optional 'minio' package") from exc

    return Minio(
        settings.endpoint,
        access_key=settings.access_key,
        secret_key=settings.secret_key,
        secure=settings.secure,
    )
