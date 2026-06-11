"""Placeholder HWPX generation for local PDF/DOCX route validation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile


PLACEHOLDER_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PlaceholderHwpxResult:
    output_hwpx: str
    source_docx_sha256: str
    source_docx_size: int


def generate_placeholder_hwpx(
    *,
    marker_docx_path: Path,
    output_hwpx_path: Path,
    job_id: str,
    input_type: str,
    object_prefix: str,
) -> PlaceholderHwpxResult:
    if marker_docx_path.suffix.lower() != ".docx":
        raise ValueError(f"pdf2hwpx placeholder requires a marker .docx input, got {marker_docx_path}")
    if not marker_docx_path.is_file():
        raise ValueError(f"marker DOCX does not exist: {marker_docx_path}")

    marker_bytes = marker_docx_path.read_bytes()
    digest = hashlib.sha256(marker_bytes).hexdigest()
    metadata = {
        "schema_version": PLACEHOLDER_SCHEMA_VERSION,
        "placeholder": True,
        "stage": "pdf2hwpx",
        "job_id": job_id,
        "input_type": input_type,
        "object_prefix": object_prefix,
        "source_marker_docx_name": marker_docx_path.name,
        "source_docx_sha256": digest,
        "source_docx_size": len(marker_bytes),
        "note": "Placeholder HWPX package. Replace with the custom pdf2hwpx library when available.",
    }

    output_hwpx_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_hwpx_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/hwpx+zip")
        archive.writestr(
            "placeholder.json",
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        )
        archive.writestr("source/marker.docx", marker_bytes)

    return PlaceholderHwpxResult(
        output_hwpx=str(output_hwpx_path),
        source_docx_sha256=digest,
        source_docx_size=len(marker_bytes),
    )


def read_placeholder_metadata(hwpx_path: Path) -> dict[str, object]:
    with zipfile.ZipFile(hwpx_path, "r") as archive:
        payload = json.loads(archive.read("placeholder.json").decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{hwpx_path} placeholder.json must contain a JSON object")
    return payload
