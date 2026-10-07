from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .models import StatementSummary

CENT = Decimal("0.01")


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
    debits = Decimal(str(rows["debit"].fillna(0).sum())) if not rows.empty else Decimal("0")
    credits = Decimal(str(rows["credit"].fillna(0).sum())) if not rows.empty else Decimal("0")
    expected_close = statement.opening_balance + credits - debits
    difference = statement.closing_balance - expected_close
    passed = abs(difference) <= CENT

    return {
        "source_file": statement.source_file,
        "check": "balance_reconciliation",
        "status": "PASS" if passed else "FAIL",
        "detail": "Opening + credits - debits matches closing balance." if passed else "Statement totals do not reconcile.",
        "difference": float(difference),
    }
