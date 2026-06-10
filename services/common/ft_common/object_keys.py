"""MinIO object key helpers for the required project convention."""

from __future__ import annotations

from datetime import date, datetime

STAGE_ARTIFACTS = {
    "input_original_pdf": "input/original.pdf",
    "input_original_docx": "input/original.docx",
    "input_original_hwpx": "input/original.hwpx",
    "pdf2docx_converted_docx": "01_pdf2docx/converted.docx",
    "extract_text_units": "02_extract/text_units.json",
    "translate_translated_units": "03_translate/translated_units.json",
    "replace_translated_docx": "04_replace/translated.docx",
    "replace_translated_hwpx": "04_replace/translated.hwpx",
    "export_final_docx": "05_export/final.docx",
    "export_final_pdf": "05_export/final.pdf",
    "export_marker_docx": "05_export/marker.docx",
    "hwpx_final": "06_hwpx/final.hwpx",
    "pdf2docx_report_json": "reports/pdf2docx.report.json",
    "pdf2docx_report_md": "reports/pdf2docx.report.md",
}


def date_prefix(value: date | datetime) -> str:
    return value.strftime("%Y-%m-%d")


def job_prefix(value: date | datetime, user_id: str, file_id: str) -> str:
    _validate_segment("user_id", user_id)
    _validate_segment("file_id", file_id)
    return f"{date_prefix(value)}/{user_id}/{file_id}"


def artifact_key(value: date | datetime, user_id: str, file_id: str, artifact_path: str) -> str:
    clean_path = artifact_path.strip("/")
    if not clean_path or ".." in clean_path.split("/"):
        raise ValueError("artifact_path must be a relative object path")
    return f"{job_prefix(value, user_id, file_id)}/{clean_path}"


def default_artifact_key(value: date | datetime, user_id: str, file_id: str, artifact_name: str) -> str:
    try:
        artifact_path = STAGE_ARTIFACTS[artifact_name]
    except KeyError as exc:
        raise KeyError(f"unknown artifact name: {artifact_name}") from exc
    return artifact_key(value, user_id, file_id, artifact_path)


def _validate_segment(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} is required")
    if "/" in value or value in {".", ".."}:
        raise ValueError(f"{name} must be a single path segment")
