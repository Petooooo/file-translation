"""DOCX text extraction for docx-extract-worker."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


SCHEMA_VERSION = "1.0"
DOCUMENT_XML_PATH = "word/document.xml"
DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_P = f"{{{DOCX_NAMESPACE}}}p"
W_R = f"{{{DOCX_NAMESPACE}}}r"
W_T = f"{{{DOCX_NAMESPACE}}}t"


@dataclass(frozen=True)
class ExtractedTextUnit:
    uid: str
    text: str
    paragraph_index: int
    run_index: int
    text_index: int

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "text": self.text,
            "location": {
                "type": "docx_run",
                "path": DOCUMENT_XML_PATH,
                "paragraph_index": self.paragraph_index,
                "run_index": self.run_index,
                "text_index": self.text_index,
            },
        }


def extract_text_units_from_docx(
    docx_path: Path,
    *,
    job_id: str,
    input_type: str,
    source_lang: str,
    target_lang: str,
) -> dict[str, object]:
    """Extract translatable DOCX text units from the main document part."""

    if docx_path.suffix.lower() != ".docx":
        raise ValueError(f"docx_extract requires a .docx input, got {docx_path}")
    document_xml = _read_document_xml(docx_path)
    root = ET.fromstring(document_xml)

    units: list[ExtractedTextUnit] = []
    for paragraph_index, paragraph in enumerate(root.iter(W_P)):
        for run_index, run in enumerate(paragraph.iter(W_R)):
            for text_index, text_node in enumerate(run.iter(W_T)):
                text = text_node.text or ""
                if not text.strip():
                    continue
                units.append(
                    ExtractedTextUnit(
                        uid=f"unit-{len(units) + 1:06d}",
                        text=text,
                        paragraph_index=paragraph_index,
                        run_index=run_index,
                        text_index=text_index,
                    )
                )

    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "input_type": input_type,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "units": [unit.to_dict() for unit in units],
    }


def write_text_units_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_document_xml(docx_path: Path) -> bytes:
    if not docx_path.exists():
        raise FileNotFoundError(docx_path)
    try:
        with zipfile.ZipFile(docx_path) as archive:
            return archive.read(DOCUMENT_XML_PATH)
    except KeyError as exc:
        raise ValueError(f"DOCX does not contain {DOCUMENT_XML_PATH}") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid DOCX zip file: {docx_path}") from exc

