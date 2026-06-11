"""HWPX export helpers for the direct HWPX route."""

from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

from libreoffice_worker.export import _write_placeholder_pdf


def export_hwpx_artifacts(
    *,
    input_hwpx_path: Path,
    final_hwpx_path: Path,
    final_docx_path: Path,
    final_pdf_path: Path,
    h2o_export_enabled: bool = False,
) -> dict[str, object]:
    if input_hwpx_path.suffix.lower() != ".hwpx":
        raise ValueError(f"hwpx_export requires a .hwpx input, got {input_hwpx_path}")
    if not input_hwpx_path.is_file():
        raise ValueError(f"input HWPX does not exist: {input_hwpx_path}")

    final_hwpx_path.parent.mkdir(parents=True, exist_ok=True)
    final_docx_path.parent.mkdir(parents=True, exist_ok=True)
    final_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_hwpx_path, final_hwpx_path)

    if h2o_export_enabled:
        raise RuntimeError("LibreOffice H2O/HWPX export is not implemented in the local skeleton")

    _write_placeholder_docx(
        final_docx_path,
        [
            "File Translation placeholder DOCX",
            f"Source HWPX: {input_hwpx_path.name}",
            "HWPX export artifact flow is validated.",
            "Validate LibreOffice H2O/HWPX export before enabling real conversion.",
        ],
    )
    _write_placeholder_pdf(
        final_pdf_path,
        [
            "File Translation placeholder PDF",
            f"Source HWPX: {input_hwpx_path.name}",
            "HWPX export artifact flow is validated.",
            "Validate LibreOffice H2O/HWPX export before enabling real conversion.",
        ],
    )

    return {
        "h2o_export_enabled": h2o_export_enabled,
        "final_hwpx": str(final_hwpx_path),
        "final_docx": str(final_docx_path),
        "final_pdf": str(final_pdf_path),
    }


def _write_placeholder_docx(path: Path, lines: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{_xml_escape(line)}</w:t></w:r></w:p>" for line in lines)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document_xml)


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
