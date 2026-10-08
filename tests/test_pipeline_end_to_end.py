from __future__ import annotations

import fitz

from consolidated_state.pipeline import process_statements


def _sectioned_pdf(
    *,
    account: str = "1111",
    currency: str | None = None,
    period: str | None = None,
    credit_date: str = "01/13/26",
    debit_date: str = "01/14/26",
) -> bytes:
    document = fitz.open()
    page = document.new_page()

    lines = [
        (40, 20, f"Account # {account}"),
    ]
    if currency:
        lines.append((40, 32, f"Currency: {currency}"))
    if period:
        lines.append((40, 44, period))

    lines.extend(
        [
            (40, 60, "Beginning balance"),
            (500, 60, "$1,000.00"),
            (40, 100, "Deposits and other additions"),
            (40, 120, "Date"),
            (150, 120, "Description"),
            (520, 120, "Amount"),
            (40, 140, credit_date),
            (150, 140, "Payroll"),
            (520, 140, "100.00"),
            (40, 180, "Withdrawals and other subtractions"),
            (40, 200, "Date"),
            (150, 200, "Description"),
            (520, 200, "Amount"),
            (40, 220, debit_date),
            (150, 220, "Coffee"),
            (520, 220, "5.00"),
            (40, 260, "Ending balance"),
            (500, 260, "$1,095.00"),
        ]
    )

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
    assert result.combined_currency is None
    assert len(result.currency_summary) == 1
    assert result.excel_report is not None
    assert result.excel_report[:2] == b"PK"
    assert result.pdf_report is not None
    assert result.pdf_report.startswith(b"%PDF")


def test_complete_pipeline_allows_multiple_accounts_and_separates_currencies():
    usd = _sectioned_pdf(
        account="1111",
        currency="USD",
        period="Statement Period: From Date: 01-JAN-26 To Date 31-JAN-26",
        credit_date="01/13/26",
        debit_date="01/14/26",
    )
    eur = _sectioned_pdf(
        account="2222",
        currency="EUR",
        period="Statement Period: From Date: 01-FEB-26 To Date 28-FEB-26",
        credit_date="13/02/26",
        debit_date="14/02/26",
    )

    result = process_statements(
        [
            ("usd.pdf", usd),
            ("eur.pdf", eur),
        ]
    )

    assert result.safe_to_export is True
    assert result.total_credits is None
    assert result.total_debits is None
    assert result.net_change is None
    assert set(result.currency_summary["currency"]) == {"USD", "EUR"}

    statuses = {
        row["check"]: row["status"]
        for _, row in result.validation.iterrows()
    }
    assert statuses["account_consistency"] == "WARNING"
    assert statuses["currency_consistency"] == "WARNING"
    assert statuses["statement_period_overlap"] == "SKIPPED"

    assert result.excel_report is not None
    assert result.pdf_report is not None


def test_complete_pipeline_keeps_known_and_unknown_currency_totals_separate():
    known = _sectioned_pdf(
        account="1111",
        currency="USD",
        period="Statement Period: From Date: 01-JAN-26 To Date 31-JAN-26",
        credit_date="01/13/26",
        debit_date="01/14/26",
    )
    unknown = _sectioned_pdf(
        account="2222",
        period="Statement Period: From Date: 01-FEB-26 To Date 28-FEB-26",
        credit_date="13/02/26",
        debit_date="14/02/26",
    )

    result = process_statements(
        [
            ("known.pdf", known),
            ("unknown.pdf", unknown),
        ]
    )

    assert result.safe_to_export is True
    assert result.total_credits is None
    assert result.total_debits is None
    assert set(result.currency_summary["currency"]) == {
        "USD",
        "Unknown (unknown.pdf)",
    }

    statuses = {
        row["check"]: row["status"]
        for _, row in result.validation.iterrows()
    }
    assert statuses["account_consistency"] == "WARNING"
    assert statuses["currency_consistency"] == "WARNING"
    assert statuses["statement_period_gaps"] == "SKIPPED"


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
