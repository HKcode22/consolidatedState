from __future__ import annotations

import fitz

from consolidated_state.layout import extract_document_layout
from consolidated_state.metadata import extract_statement_metadata


def _pdf_bytes(lines):
    document = fitz.open()
    page = document.new_page()
    for x, y, text in lines:
        page.insert_text((x, y), text, fontsize=9)
    data = document.tobytes()
    document.close()
    return data


def test_metadata_supports_account_ending_in_and_dmy_numeric_period():
    data = _pdf_bytes(
        [
            (40, 30, "Account ending in 4321"),
            (40, 50, "Currency: GBP"),
            (40, 70, "Statement Period 13/01/2026 - 31/01/2026"),
        ]
    )

    metadata = extract_statement_metadata(
        extract_document_layout(data)
    )

    assert metadata.account_fingerprint is not None
    assert metadata.currency == "GBP"
    assert metadata.statement_start.isoformat() == "2026-01-13"
    assert metadata.statement_end.isoformat() == "2026-01-31"


def test_metadata_supports_mdy_numeric_period_when_unambiguous():
    data = _pdf_bytes(
        [
            (40, 30, "Account No: XXXX9876"),
            (40, 50, "Statement Period 01/13/2026 - 01/31/2026"),
        ]
    )

    metadata = extract_statement_metadata(
        extract_document_layout(data)
    )

    assert metadata.account_fingerprint is not None
    assert metadata.statement_start.isoformat() == "2026-01-13"
    assert metadata.statement_end.isoformat() == "2026-01-31"


def test_metadata_refuses_ambiguous_numeric_period():
    data = _pdf_bytes(
        [
            (40, 30, "Statement Period 01/02/2026 - 01/10/2026"),
        ]
    )

    metadata = extract_statement_metadata(
        extract_document_layout(data)
    )

    assert metadata.statement_start is None
    assert metadata.statement_end is None
