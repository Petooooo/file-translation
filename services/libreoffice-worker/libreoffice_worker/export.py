"""DOCX export helpers for the DOCX route."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


VALID_PDF_MODES = {"placeholder", "libreoffice"}


def export_docx_artifacts(
    *,
    input_docx_path: Path,
    final_docx_path: Path,
    final_pdf_path: Path,
    pdf_mode: str = "placeholder",
    libreoffice_binary: str = "soffice",
) -> dict[str, object]:
    if input_docx_path.suffix.lower() != ".docx":
        raise ValueError(f"docx_export requires a .docx input, got {input_docx_path}")
    if not input_docx_path.is_file():
        raise ValueError(f"input DOCX does not exist: {input_docx_path}")

    mode = pdf_mode.lower().strip()
    if mode not in VALID_PDF_MODES:
        allowed = ", ".join(sorted(VALID_PDF_MODES))
        raise ValueError(f"pdf_mode must be one of: {allowed}")

    final_docx_path.parent.mkdir(parents=True, exist_ok=True)
    final_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_docx_path, final_docx_path)

    if mode == "libreoffice":
        _export_pdf_with_libreoffice(input_docx_path, final_pdf_path, libreoffice_binary)
    else:
        _write_placeholder_pdf(
            final_pdf_path,
            [
                "File Translation placeholder PDF",
                f"Source DOCX: {input_docx_path.name}",
                "DOCX export artifact flow is validated.",
                "Enable DOCX_EXPORT_PDF_MODE=libreoffice for real PDF export.",
            ],
        )

    return {
        "pdf_mode": mode,
        "final_docx": str(final_docx_path),
        "final_pdf": str(final_pdf_path),
    }


def _export_pdf_with_libreoffice(input_docx_path: Path, final_pdf_path: Path, libreoffice_binary: str) -> None:
    binary = shutil.which(libreoffice_binary) or libreoffice_binary
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        command = [
            binary,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_docx_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "LibreOffice conversion failed").strip()
            raise RuntimeError(f"LibreOffice PDF export failed: {detail}")

        generated_pdf = output_dir / f"{input_docx_path.stem}.pdf"
        if not generated_pdf.is_file():
            raise RuntimeError(f"LibreOffice did not create expected PDF: {generated_pdf}")
        shutil.copy2(generated_pdf, final_pdf_path)


def _write_placeholder_pdf(path: Path, lines: list[str]) -> None:
    commands = ["BT", "/F1 12 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            commands.append("0 -18 Td")
        commands.append(f"({_pdf_escape(line)}) Tj")
    commands.append("ET")
    content_stream = "\n".join(commands).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content_stream)).encode("ascii")
        + b" >>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(bytes(pdf))


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
