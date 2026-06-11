"""Local HWPX text extraction/replacement stub.

The closed-network target should use rhwp for semantic HWPX handling. This
module intentionally keeps a small zip/XML implementation so the HWPX route can
be tested locally before rhwp and LibreOffice H2O support are available.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET


SCHEMA_VERSION = "1.0"
LOCATION_TYPE = "hwpx_xml_text"
SAMPLE_SECTION_PATH = "Contents/section0.xml"


def create_sample_hwpx(path: Path, texts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    paragraph_nodes = "".join(f"<p><t>{_xml_escape(text)}</t></p>" for text in texts)
    section_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<section>"
        f"{paragraph_nodes}"
        "</section>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/hwpx+zip")
        archive.writestr(SAMPLE_SECTION_PATH, section_xml)


def extract_text_units_from_hwpx(
    hwpx_path: Path,
    *,
    job_id: str,
    input_type: str,
    source_lang: str,
    target_lang: str,
) -> dict[str, object]:
    if hwpx_path.suffix.lower() != ".hwpx":
        raise ValueError(f"hwpx_extract requires a .hwpx input, got {hwpx_path}")
    if input_type != "hwpx":
        raise ValueError(f"hwpx_extract requires input_type 'hwpx', got {input_type!r}")

    units: list[dict[str, object]] = []
    try:
        with zipfile.ZipFile(hwpx_path, "r") as archive:
            for xml_path in _xml_member_names(archive):
                units.extend(_extract_xml_units(archive.read(xml_path), xml_path, len(units)))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid HWPX zip file: {hwpx_path}") from exc

    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "input_type": input_type,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "units": units,
    }


def write_text_units_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json_file(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def replace_hwpx_text_units(
    *,
    input_hwpx_path: Path,
    text_units_path: Path,
    translated_units_path: Path,
    output_hwpx_path: Path,
) -> dict[str, object]:
    if input_hwpx_path.suffix.lower() != ".hwpx":
        raise ValueError(f"hwpx_replace requires a .hwpx input, got {input_hwpx_path}")

    text_units_payload = read_json_file(text_units_path)
    translated_units_payload = read_json_file(translated_units_path)
    replacements = _build_replacements(text_units_payload, translated_units_payload)

    output_hwpx_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_output = Path(temp_dir) / "translated.hwpx"
        replaced_units = _write_replaced_hwpx(input_hwpx_path, temp_output, replacements)
        shutil.move(str(temp_output), output_hwpx_path)

    return {
        "replaced_units": replaced_units,
        "output_hwpx": str(output_hwpx_path),
    }


def _extract_xml_units(xml_payload: bytes, xml_path: str, uid_offset: int) -> list[dict[str, object]]:
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise ValueError(f"HWPX XML member is not parseable: {xml_path}") from exc

    units: list[dict[str, object]] = []
    element_index = 0
    for node in root.iter():
        text = node.text or ""
        if not text.strip():
            continue
        units.append(
            {
                "uid": f"unit-{uid_offset + len(units) + 1:06d}",
                "text": text,
                "location": {
                    "type": LOCATION_TYPE,
                    "path": xml_path,
                    "element_index": element_index,
                },
            }
        )
        element_index += 1
    return units


def _build_replacements(
    text_units_payload: dict[str, object],
    translated_units_payload: dict[str, object],
) -> dict[str, dict[int, str]]:
    text_units = text_units_payload.get("units")
    translated_units = translated_units_payload.get("units")
    if not isinstance(text_units, list):
        raise ValueError("text_units.json field 'units' must be a list")
    if not isinstance(translated_units, list):
        raise ValueError("translated_units.json field 'units' must be a list")

    translated_by_uid: dict[str, str] = {}
    for unit in translated_units:
        if not isinstance(unit, dict):
            raise ValueError("each translated unit must be an object")
        if str(unit.get("status", "translated")) != "translated":
            continue
        uid = str(unit.get("uid", ""))
        if uid:
            translated_by_uid[uid] = str(unit.get("translated", ""))

    replacements: dict[str, dict[int, str]] = {}
    for unit in text_units:
        if not isinstance(unit, dict):
            raise ValueError("each text unit must be an object")
        uid = str(unit.get("uid", ""))
        if uid not in translated_by_uid:
            continue
        location = unit.get("location")
        if not isinstance(location, dict):
            raise ValueError(f"text unit {uid!r} is missing location metadata")
        if location.get("type") != LOCATION_TYPE:
            raise ValueError(f"text unit {uid!r} has unsupported location type {location.get('type')!r}")
        xml_path = str(location.get("path", ""))
        if not xml_path.endswith(".xml"):
            raise ValueError(f"text unit {uid!r} has unsupported HWPX path {xml_path!r}")
        element_index = int(location["element_index"])
        replacements.setdefault(xml_path, {})[element_index] = translated_by_uid[uid]
    return replacements


def _write_replaced_hwpx(
    input_hwpx_path: Path,
    output_hwpx_path: Path,
    replacements: dict[str, dict[int, str]],
) -> int:
    try:
        with zipfile.ZipFile(input_hwpx_path, "r") as source:
            with zipfile.ZipFile(output_hwpx_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
                replaced_units = 0
                for info in source.infolist():
                    payload = source.read(info.filename)
                    if info.filename in replacements:
                        payload, replaced_count = _replace_xml_payload(
                            payload,
                            replacements[info.filename],
                            info.filename,
                        )
                        replaced_units += replaced_count
                    target.writestr(info, payload)
                return replaced_units
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid HWPX zip file: {input_hwpx_path}") from exc


def _replace_xml_payload(
    xml_payload: bytes,
    replacements: dict[int, str],
    xml_path: str,
) -> tuple[bytes, int]:
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise ValueError(f"HWPX XML member is not parseable: {xml_path}") from exc

    replaced = 0
    element_index = 0
    for node in root.iter():
        text = node.text or ""
        if not text.strip():
            continue
        if element_index in replacements:
            node.text = replacements[element_index]
            replaced += 1
        element_index += 1
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), replaced


def _xml_member_names(archive: zipfile.ZipFile) -> list[str]:
    return sorted(
        info.filename
        for info in archive.infolist()
        if not info.is_dir() and info.filename.lower().endswith(".xml")
    )


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
