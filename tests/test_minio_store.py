from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))

from ft_common.config import load_config
from ft_common.minio_store import MinioArtifactStore, MinioConnectionSettings, normalize_minio_endpoint


class FakeMinioClient:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, str, str]] = []
        self.uploads: list[tuple[str, str, str, dict[str, object]]] = []

    def fget_object(self, bucket: str, object_key: str, destination: str) -> None:
        self.downloads.append((bucket, object_key, destination))
        Path(destination).write_bytes(b"data")

    def fput_object(self, bucket: str, object_key: str, source: str, **kwargs: object) -> None:
        self.uploads.append((bucket, object_key, source, kwargs))


class MinioStoreTests(unittest.TestCase):
    def test_normalize_endpoint_parses_http_and_https(self) -> None:
        self.assertEqual(normalize_minio_endpoint("http://minio:9000"), ("minio:9000", False))
        self.assertEqual(normalize_minio_endpoint("https://minio.example"), ("minio.example", True))
        self.assertEqual(normalize_minio_endpoint("minio:9000"), ("minio:9000", False))

    def test_settings_from_config_uses_secret_fields(self) -> None:
        config = load_config(
            "pdf2docx-worker",
            "worker",
            "pdf2docx",
            env={
                "MINIO_ENDPOINT": "https://minio.internal",
                "MINIO_BUCKET": "file-translation",
                "MINIO_ACCESS_KEY": "access",
                "MINIO_SECRET_KEY": "secret",
            },
        )

        settings = MinioConnectionSettings.from_config(config)

        self.assertEqual(settings.endpoint, "minio.internal")
        self.assertTrue(settings.secure)
        self.assertEqual(settings.access_key, "access")
        self.assertEqual(settings.secret_key, "secret")

    def test_store_download_and_upload_delegate_to_client(self) -> None:
        fake_client = FakeMinioClient()
        store = MinioArtifactStore(
            MinioConnectionSettings("minio:9000", "file-translation", "access", "secret", False),
            client=fake_client,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = Path(temp_dir) / "download" / "input.pdf"
            upload_path = Path(temp_dir) / "output.docx"
            upload_path.write_bytes(b"docx")

            store.download_file("prefix/input/original.pdf", download_path)
            store.upload_file("prefix/01_pdf2docx/converted.docx", upload_path, "docx/type")

        self.assertEqual(fake_client.downloads[0][0], "file-translation")
        self.assertEqual(fake_client.downloads[0][1], "prefix/input/original.pdf")
        self.assertEqual(fake_client.uploads[0][1], "prefix/01_pdf2docx/converted.docx")
        self.assertEqual(fake_client.uploads[0][3]["content_type"], "docx/type")


if __name__ == "__main__":
    unittest.main()
