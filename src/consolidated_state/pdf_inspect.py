from __future__ import annotations

import hashlib

import fitz

from .models import PdfInspection

MAX_PDF_BYTES = 20 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_and_extract_pdf(pdf_bytes: bytes, source_file: str) -> tuple[PdfInspection, str]:
    """Inspect a PDF and extract embedded text without intentionally persisting it."""
    digest = sha256_bytes(pdf_bytes)
    size_bytes = len(pdf_bytes)

    if size_bytes == 0:
        return (
            PdfInspection(source_file, digest, 0, 0, False, False, "ERROR", "The uploaded file is empty."),
            "",
        )

    if size_bytes > MAX_PDF_BYTES:
        return (
            PdfInspection(
                source_file,
                digest,
                size_bytes,
                0,
                False,
                False,
                "TOO_LARGE",
                "File exceeds the 20 MB MVP limit.",
            ),
            "",
        )

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            page_count = document.page_count
            if document.needs_pass:
                return (
                    PdfInspection(
                        source_file,
                        digest,
                        size_bytes,
                        page_count,
                        True,
                        False,
                        "PASSWORD_REQUIRED",
                        "PDF is encrypted/password-protected.",
                    ),
                    "",
                )

            text = "\n".join(page.get_text("text") for page in document)
            has_text = bool(text.strip())
            if has_text:
                status = "TEXT_READY"
                detail = "Embedded PDF text is available for a bank-specific parser."
            else:
                status = "OCR_REQUIRED"
                detail = "No embedded text found; this statement may be scanned and require OCR."

            return (
                PdfInspection(
                    source_file,
                    digest,
                    size_bytes,
                    page_count,
                    False,
                    has_text,
                    status,
                    detail,
                ),
                text,
            )
    except Exception:
        return (
            PdfInspection(
                source_file,
                digest,
                size_bytes,
                0,
                False,
                False,
                "INVALID_PDF",
                "The file could not be read as a PDF.",
            ),
            "",
        )
