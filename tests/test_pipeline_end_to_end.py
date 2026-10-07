from __future__ import annotations

import fitz

from consolidated_state.pipeline import process_statements


def _sectioned_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()

    lines = [
        (40, 40, "Beginning balance"),
        (500, 40, "$1,000.00"),
        (40, 80, "Deposits and other additions"),
        (40, 100, "Date"),
        (150, 100, "Description"),
        (520, 100, "Amount"),
        (40, 120, "01/13/26"),
        (150, 120, "Payroll"),
        (520, 120, "100.00"),
        (40, 160, "Withdrawals and other subtractions"),
        (40, 180, "Date"),
        (150, 180, "Description"),
        (520, 180, "Amount"),
        (40, 200, "01/14/26"),
        (150, 200, "Coffee"),
        (520, 200, "5.00"),
        (40, 240, "Ending balance"),
        (500, 240, "$1,095.00"),
    ]

    for x, y, text in lines:
        page.insert_text((x, y), text, fontsize=9)

    data = document.tobytes()
    document.close()
    return data


def test_complete_pipeline_builds_reports_for_valid_statement():
    result = process_statements(
        [("january.pdf", _sectioned_pdf())]
    )

    assert result.safe_to_export is True
    assert len(result.transactions) == 2
    assert str(result.total_credits) == "100.00"
    assert str(result.total_debits) == "5.00"
    assert result.excel_report is not None
    assert result.excel_report[:2] == b"PK"
    assert result.pdf_report is not None
    assert result.pdf_report.startswith(b"%PDF")


def test_complete_pipeline_blocks_exact_duplicate_pdfs():
    data = _sectioned_pdf()

    result = process_statements(
        [
            ("january.pdf", data),
            ("january-copy.pdf", data),
        ]
    )

    assert result.safe_to_export is False
    assert result.excel_report is None
    assert result.pdf_report is None
    assert any(
        "DUPLICATE_FILE" in reason
        for reason in result.blocking_reasons
    )
