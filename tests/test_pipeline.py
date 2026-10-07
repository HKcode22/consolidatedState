from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

from consolidated_state.consolidate import find_duplicate_transactions, monthly_summary, transactions_to_frame
from consolidated_state.export_excel import build_excel_report
from consolidated_state.models import StatementSummary, Transaction
from consolidated_state.validate import reconcile_statement, validate_transaction_rows


def sample_transactions():
    return [
        Transaction(date(2026, 1, 2), "Deposit", credit=Decimal("100.00"), source_file="jan.pdf", statement_period="2026-01"),
        Transaction(date(2026, 1, 3), "Coffee", debit=Decimal("5.00"), source_file="jan.pdf", statement_period="2026-01"),
    ]


def test_monthly_summary_and_reconciliation():
    frame = transactions_to_frame(sample_transactions())
    summary = monthly_summary(frame)
    assert summary.iloc[0]["total_debits"] == Decimal("5.00")
    assert summary.iloc[0]["total_credits"] == Decimal("100.00")
    assert summary.iloc[0]["net"] == Decimal("95.00")

    statement = StatementSummary("jan.pdf", "2026-01", Decimal("1000.00"), Decimal("1095.00"))
    result = reconcile_statement(statement, frame)
    assert result["status"] == "PASS"
    assert result["difference"] == Decimal("0.00")


def test_decimal_math_is_exact_at_cent_level():
    transactions = [
        Transaction(date(2026, 1, 1), "A", debit=Decimal("0.10"), source_file="jan.pdf"),
        Transaction(date(2026, 1, 2), "B", debit=Decimal("0.20"), source_file="jan.pdf"),
        Transaction(date(2026, 1, 3), "C", credit=Decimal("0.30"), source_file="jan.pdf"),
    ]
    summary = monthly_summary(transactions_to_frame(transactions))
    assert summary.iloc[0]["total_debits"] == Decimal("0.30")
    assert summary.iloc[0]["total_credits"] == Decimal("0.30")
    assert summary.iloc[0]["net"] == Decimal("0.00")


def test_transaction_integrity_accepts_valid_rows():
    result = validate_transaction_rows(transactions_to_frame(sample_transactions()))
    assert result["status"] == "PASS"


def test_transaction_integrity_rejects_both_debit_and_credit():
    bad = Transaction(
        date(2026, 1, 4),
        "Invalid row",
        debit=Decimal("1.00"),
        credit=Decimal("1.00"),
        source_file="jan.pdf",
    )
    result = validate_transaction_rows(transactions_to_frame([bad]))
    assert result["status"] == "FAIL"
    assert "invalid_amount_sides=1" in result["detail"]


def test_transaction_integrity_rejects_negative_amount():
    bad = Transaction(
        date(2026, 1, 4),
        "Invalid row",
        debit=Decimal("-1.00"),
        source_file="jan.pdf",
    )
    result = validate_transaction_rows(transactions_to_frame([bad]))
    assert result["status"] == "FAIL"
    assert "negative_amount=1" in result["detail"]


def test_duplicate_detection_across_source_statements():
    first = Transaction(date(2026, 1, 2), "Same", debit=Decimal("10.00"), source_file="a.pdf")
    second = Transaction(date(2026, 1, 2), "Same", debit=Decimal("10.00"), source_file="b.pdf")
    frame = transactions_to_frame([first, second])
    assert len(find_duplicate_transactions(frame)) == 2


def test_repeated_transaction_inside_one_statement_is_not_automatically_duplicate():
    first = Transaction(date(2026, 1, 2), "Same", debit=Decimal("10.00"), balance=Decimal("90.00"), source_file="a.pdf")
    second = Transaction(date(2026, 1, 2), "Same", debit=Decimal("10.00"), balance=Decimal("80.00"), source_file="a.pdf")
    frame = transactions_to_frame([first, second])
    assert find_duplicate_transactions(frame).empty


def test_excel_contains_expected_sheets():
    transactions = transactions_to_frame(sample_transactions())
    summary = monthly_summary(transactions)
    validation = pd.DataFrame([{"source_file": "jan.pdf", "check": "test", "status": "PASS", "detail": "ok", "difference": Decimal("0.00")}])
    data = build_excel_report(transactions, summary, validation)
    workbook = load_workbook(BytesIO(data))
    assert workbook.sheetnames == ["About", "Transactions", "Monthly Summary", "Validation"]
