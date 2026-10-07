from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

from consolidated_state.consolidate import find_duplicate_transactions, monthly_summary, transactions_to_frame
from consolidated_state.export_excel import build_excel_report
from consolidated_state.models import StatementSummary, Transaction
from consolidated_state.validate import reconcile_statement


def sample_transactions():
    return [
        Transaction(date(2026, 1, 2), "Deposit", credit=Decimal("100.00"), source_file="jan.pdf", statement_period="2026-01"),
        Transaction(date(2026, 1, 3), "Coffee", debit=Decimal("5.00"), source_file="jan.pdf", statement_period="2026-01"),
    ]


def test_monthly_summary_and_reconciliation():
    frame = transactions_to_frame(sample_transactions())
    summary = monthly_summary(frame)
    assert summary.iloc[0]["total_debits"] == 5.0
    assert summary.iloc[0]["total_credits"] == 100.0
    assert summary.iloc[0]["net"] == 95.0

    statement = StatementSummary("jan.pdf", "2026-01", Decimal("1000.00"), Decimal("1095.00"))
    result = reconcile_statement(statement, frame)
    assert result["status"] == "PASS"
    assert result["difference"] == 0.0


def test_duplicate_detection():
    tx = Transaction(date(2026, 1, 2), "Same", debit=Decimal("10.00"), source_file="a.pdf")
    frame = transactions_to_frame([tx, tx])
    assert len(find_duplicate_transactions(frame)) == 2


def test_excel_contains_expected_sheets():
    transactions = transactions_to_frame(sample_transactions())
    summary = monthly_summary(transactions)
    validation = pd.DataFrame([{"source_file": "jan.pdf", "check": "test", "status": "PASS", "detail": "ok", "difference": 0.0}])
    data = build_excel_report(transactions, summary, validation)
    workbook = load_workbook(BytesIO(data))
    assert workbook.sheetnames == ["About", "Transactions", "Monthly Summary", "Validation"]
