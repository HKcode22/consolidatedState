from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .models import StatementSummary

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _sum_money(series: pd.Series) -> Decimal:
    total = ZERO
    for value in series:
        if value is None or pd.isna(value):
            continue
        total += value if isinstance(value, Decimal) else Decimal(str(value))
    return total


def reconcile_statement(statement: StatementSummary, frame: pd.DataFrame) -> dict[str, object]:
    """Reconcile one statement when both opening and closing balances are known."""
    if statement.opening_balance is None or statement.closing_balance is None:
        return {
            "source_file": statement.source_file,
            "check": "balance_reconciliation",
            "status": "SKIPPED",
            "detail": "Opening/closing balance not available from the parser.",
            "difference": None,
        }

    rows = frame[frame["source_file"] == statement.source_file] if not frame.empty else frame
    debits = _sum_money(rows["debit"]) if not rows.empty else ZERO
    credits = _sum_money(rows["credit"]) if not rows.empty else ZERO
    expected_close = statement.opening_balance + credits - debits
    difference = statement.closing_balance - expected_close
    passed = abs(difference) <= CENT

    return {
        "source_file": statement.source_file,
        "check": "balance_reconciliation",
        "status": "PASS" if passed else "FAIL",
        "detail": "Opening + credits - debits matches closing balance." if passed else "Statement totals do not reconcile.",
        "difference": difference,
    }
