"""DOCX text replacement using text unit locations and translated units."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET


DOCUMENT_XML_PATH = "word/document.xml"
DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_P = f"{{{DOCX_NAMESPACE}}}p"
W_R = f"{{{DOCX_NAMESPACE}}}r"
W_T = f"{{{DOCX_NAMESPACE}}}t"

ET.register_namespace("w", DOCX_NAMESPACE)


@dataclass(frozen=True)
class Replacement:
    uid: str
    translated: str
    paragraph_index: int
    run_index: int
    text_index: int


def read_json_file(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def replace_docx_text_units(
    *,
    input_docx_path: Path,
    text_units_path: Path,
    translated_units_path: Path,
    output_docx_path: Path,
) -> dict[str, object]:
    if input_docx_path.suffix.lower() != ".docx":
        raise ValueError(f"docx_replace requires a .docx input, got {input_docx_path}")

    text_units_payload = read_json_file(text_units_path)
    translated_units_payload = read_json_file(translated_units_path)
    replacements = _build_replacements(text_units_payload, translated_units_payload)

    output_docx_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_output = Path(temp_dir) / "replaced.docx"
        _write_replaced_docx(input_docx_path, temp_output, replacements)
        shutil.move(str(temp_output), output_docx_path)

    return {
        "replaced_units": len(replacements),
        "output_docx": str(output_docx_path),
    }


def _build_replacements(
    text_units_payload: dict[str, object],
    translated_units_payload: dict[str, object],
) -> list[Replacement]:
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
        status = str(unit.get("status", "translated"))
        if status != "translated":
            continue
        uid = str(unit.get("uid", ""))
        if uid:
            translated_by_uid[uid] = str(unit.get("translated", ""))

    replacements: list[Replacement] = []
    for unit in text_units:
        if not isinstance(unit, dict):
            raise ValueError("each text unit must be an object")
        uid = str(unit.get("uid", ""))
        if uid not in translated_by_uid:
            continue
        location = unit.get("location")
        if not isinstance(location, dict):
            raise ValueError(f"text unit {uid!r} is missing location metadata")
        if location.get("type") != "docx_run":
            raise ValueError(f"text unit {uid!r} has unsupported location type {location.get('type')!r}")
        if location.get("path", DOCUMENT_XML_PATH) != DOCUMENT_XML_PATH:
            raise ValueError(f"text unit {uid!r} has unsupported DOCX path {location.get('path')!r}")
        replacements.append(
            Replacement(
                uid=uid,
                translated=translated_by_uid[uid],
                paragraph_index=int(location["paragraph_index"]),
                run_index=int(location["run_index"]),
                text_index=int(location.get("text_index", 0)),
            )
        )
    return replacements


def _write_replaced_docx(input_docx_path: Path, output_docx_path: Path, replacements: list[Replacement]) -> None:
    try:
        with zipfile.ZipFile(input_docx_path, "r") as source:
            document_xml = source.read(DOCUMENT_XML_PATH)
            replaced_xml = _replace_document_xml(document_xml, replacements)
            with zipfile.ZipFile(output_docx_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
                seen_document = False
                for info in source.infolist():
                    if info.filename == DOCUMENT_XML_PATH:
                        target.writestr(info, replaced_xml)
                        seen_document = True
                    else:
                        target.writestr(info, source.read(info.filename))
                if not seen_document:
                    raise ValueError(f"DOCX does not contain {DOCUMENT_XML_PATH}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid DOCX zip file: {input_docx_path}") from exc
    except KeyError as exc:
        raise ValueError(f"DOCX does not contain {DOCUMENT_XML_PATH}") from exc


def _replace_document_xml(document_xml: bytes, replacements: list[Replacement]) -> bytes:
    root = ET.fromstring(document_xml)
    paragraphs = list(root.iter(W_P))

    for replacement in replacements:
        try:
            paragraph = paragraphs[replacement.paragraph_index]
            run = list(paragraph.iter(W_R))[replacement.run_index]
            text_node = list(run.iter(W_T))[replacement.text_index]
        except IndexError as exc:
            raise ValueError(f"text unit {replacement.uid!r} location is out of range") from exc
        text_node.text = replacement.translated

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

