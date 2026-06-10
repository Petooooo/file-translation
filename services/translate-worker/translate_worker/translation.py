"""text_units.json to translated_units.json transformation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from translate_worker.provider import TranslationProvider


SCHEMA_VERSION = "1.0"
ProgressCallback = Callable[[int, int, int], None]


def read_text_units_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("text_units.json must contain a JSON object")
    return payload


def write_translated_units_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def translate_text_units(
    text_units_payload: dict[str, object],
    *,
    provider: TranslationProvider,
    source_lang: str | None = None,
    target_lang: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, object]:
    units = text_units_payload.get("units")
    if not isinstance(units, list):
        raise ValueError("text_units.json field 'units' must be a list")

    job_id = str(text_units_payload.get("job_id", "unknown"))
    input_type = str(text_units_payload.get("input_type", "docx"))
    resolved_source_lang = source_lang or str(text_units_payload.get("source_lang", "und"))
    resolved_target_lang = target_lang or str(text_units_payload.get("target_lang", "und"))

    translated_units: list[dict[str, object]] = []
    total_units = len(units)
    for index, unit in enumerate(units, start=1):
        if not isinstance(unit, dict):
            raise ValueError("each text unit must be an object")
        uid = str(unit.get("uid", f"unit-{index:06d}"))
        text = str(unit.get("text", ""))
        translated = provider.translate(
            text=text,
            uid=uid,
            source_lang=resolved_source_lang,
            target_lang=resolved_target_lang,
        )
        translated_units.append(
            {
                "uid": uid,
                "source": text,
                "translated": translated,
                "status": "translated",
            }
        )
        if progress_callback is not None:
            progress_callback(total_units, index, 0)

    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "input_type": input_type,
        "source_lang": resolved_source_lang,
        "target_lang": resolved_target_lang,
        "provider": provider.name,
        "units": translated_units,
    }

