from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Sequence

from pypdf import PdfReader


MIN_TEXT_CHARACTERS = 40
MIN_TEXT_PER_PAGE = 15


@dataclass(frozen=True)
class InspectionResult:
    filename: str
    page_count: int | None
    text_characters: int
    status: str
    details: str


def _meaningful_character_count(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def inspect_uploaded_files(files: Sequence[object]) -> list[InspectionResult]:
    """Inspect uploaded PDF bytes without writing them or extracted text to disk."""
    reports: list[InspectionResult] = []
    seen_hashes: dict[str, str] = {}

    for uploaded_file in files:
        filename = str(getattr(uploaded_file, "name", "statement.pdf"))
        payload = bytes(uploaded_file.getvalue())

        if not payload.startswith(b"%PDF-"):
            reports.append(
                InspectionResult(
                    filename=filename,
                    page_count=None,
                    text_characters=0,
                    status="Not a readable PDF",
                    details="The file does not have a valid PDF header.",
                )
            )
            continue

        digest = sha256(payload).hexdigest()
        duplicate_of = seen_hashes.get(digest)
        if duplicate_of is not None:
            reports.append(
                InspectionResult(
                    filename=filename,
                    page_count=None,
                    text_characters=0,
                    status="Duplicate",
                    details=f"Identical to {duplicate_of}; this copy was not re-inspected.",
                )
            )
            continue
        seen_hashes[digest] = filename

        try:
            reader = PdfReader(BytesIO(payload), strict=False)
            if reader.is_encrypted:
                reports.append(
                    InspectionResult(
                        filename=filename,
                        page_count=None,
                        text_characters=0,
                        status="Password-protected",
                        details="This version cannot inspect password-protected PDFs.",
                    )
                )
                continue

            page_text: list[str] = []
            for page in reader.pages:
                try:
                    page_text.append(page.extract_text() or "")
                except Exception:
                    page_text.append("")

            page_counts = [_meaningful_character_count(text) for text in page_text]
            total_characters = sum(page_counts)

            if total_characters < MIN_TEXT_CHARACTERS:
                status = "No embedded text"
                details = (
                    "No meaningful text was extracted; this may be a scanned or "
                    "image-only PDF. OCR is not enabled."
                )
            elif any(count < MIN_TEXT_PER_PAGE for count in page_counts):
                status = "Partial text"
                details = (
                    "Some pages have little or no extractable text. Completeness "
                    "cannot be confirmed."
                )
            else:
                status = "Text found"
                details = (
                    "Embedded text is present. Transaction parsing still requires "
                    "confirmation of the bank layout."
                )

            reports.append(
                InspectionResult(
                    filename=filename,
                    page_count=len(reader.pages),
                    text_characters=total_characters,
                    status=status,
                    details=details,
                )
            )
        except Exception:
            reports.append(
                InspectionResult(
                    filename=filename,
                    page_count=None,
                    text_characters=0,
                    status="Could not read PDF",
                    details="The PDF could not be inspected. No transaction data was extracted.",
                )
            )

    return reports
