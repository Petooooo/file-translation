"""DOCX marker helpers for the PDF/DOCX route."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET


DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{DOCX_NAMESPACE}}}t"

ET.register_namespace("w", DOCX_NAMESPACE)


@dataclass(frozen=True)
class MarkerResult:
    marked_text_nodes: int
    replaced_spaces: int
    output_docx: str


def mark_docx_spaces(
    *,
    input_docx_path: Path,
    marker_docx_path: Path,
    marker: str = "¡",
) -> MarkerResult:
    if input_docx_path.suffix.lower() != ".docx":
        raise ValueError(f"docx_marker requires a .docx input, got {input_docx_path}")
    if not input_docx_path.is_file():
        raise ValueError(f"input DOCX does not exist: {input_docx_path}")
    if marker == "":
        raise ValueError("marker must not be empty")

    marker_docx_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_output = Path(temp_dir) / "marker.docx"
        result = _write_marker_docx(input_docx_path, temp_output, marker)
        shutil.move(str(temp_output), marker_docx_path)

    return MarkerResult(
        marked_text_nodes=result.marked_text_nodes,
        replaced_spaces=result.replaced_spaces,
        output_docx=str(marker_docx_path),
    )


def _write_marker_docx(input_docx_path: Path, output_docx_path: Path, marker: str) -> MarkerResult:
    marked_text_nodes = 0
    replaced_spaces = 0
    try:
        with zipfile.ZipFile(input_docx_path, "r") as source:
            with zipfile.ZipFile(output_docx_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    payload = source.read(info.filename)
                    if _is_word_xml(info.filename):
                        marked_payload, node_count, space_count = _mark_xml_payload(payload, marker)
                        payload = marked_payload
                        marked_text_nodes += node_count
                        replaced_spaces += space_count
                    target.writestr(info, payload)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid DOCX zip file: {input_docx_path}") from exc

    return MarkerResult(
        marked_text_nodes=marked_text_nodes,
        replaced_spaces=replaced_spaces,
        output_docx=str(output_docx_path),
    )


def _mark_xml_payload(payload: bytes, marker: str) -> tuple[bytes, int, int]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return payload, 0, 0

    marked_text_nodes = 0
    replaced_spaces = 0
    for text_node in root.iter(W_T):
        original = text_node.text
        if original is None or " " not in original:
            continue
        space_count = original.count(" ")
        text_node.text = original.replace(" ", marker)
        marked_text_nodes += 1
        replaced_spaces += space_count

    if marked_text_nodes == 0:
        return payload, 0, 0
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), marked_text_nodes, replaced_spaces


def _is_word_xml(filename: str) -> bool:
    return filename.startswith("word/") and filename.endswith(".xml")
