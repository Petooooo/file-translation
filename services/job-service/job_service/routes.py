"""Pipeline route definitions owned by job-service."""

from __future__ import annotations

VALID_INPUT_TYPES = {"pdf", "docx", "hwpx"}

TERMINAL_STAGES = {"completed", "failed", "cancelled"}

PIPELINE_ROUTES: dict[str, list[str]] = {
    "pdf": [
        "pdf2docx",
        "docx_extract",
        "docx_translate",
        "docx_replace",
        "docx_export",
        "docx_marker",
        "pdf2hwpx",
        "email_send",
    ],
    "docx": [
        "docx_extract",
        "docx_translate",
        "docx_replace",
        "docx_export",
        "docx_marker",
        "pdf2hwpx",
        "email_send",
    ],
    "hwpx": [
        "hwpx_extract",
        "hwpx_translate",
        "hwpx_replace",
        "hwpx_export",
        "email_send",
    ],
}


def validate_input_type(input_type: str) -> str:
    normalized = input_type.lower().strip()
    if normalized not in VALID_INPUT_TYPES:
        allowed = ", ".join(sorted(VALID_INPUT_TYPES))
        raise ValueError(f"input_type must be one of: {allowed}")
    return normalized


def pipeline_route(input_type: str) -> list[str]:
    return list(PIPELINE_ROUTES[validate_input_type(input_type)])


def initial_stage(input_type: str) -> str:
    return pipeline_route(input_type)[0]


def next_stage(route: list[str], completed_stage: str) -> str | None:
    try:
        index = route.index(completed_stage)
    except ValueError as exc:
        raise ValueError(f"stage {completed_stage!r} is not in pipeline_route") from exc

    next_index = index + 1
    if next_index >= len(route):
        return None
    return route[next_index]
