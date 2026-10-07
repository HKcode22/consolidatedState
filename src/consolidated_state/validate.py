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


def _is_present(value: object) -> bool:
    return value is not None and not pd.isna(value)


def validate_transaction_rows(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {
            "source_file": "ALL",
            "check": "transaction_integrity",
            "status": "FAIL",
            "detail": "No normalized transactions were produced.",
            "difference": None,
        }

    issue_counts = {
        "missing_description": 0,
        "missing_source_file": 0,
        "invalid_amount_sides": 0,
        "negative_amount": 0,
    }

    for _, row in frame.iterrows():
        if not str(row.get("description", "")).strip():
            issue_counts["missing_description"] += 1

        if not str(row.get("source_file", "")).strip():
            issue_counts["missing_source_file"] += 1

        debit = row.get("debit")
        credit = row.get("credit")
        has_debit = _is_present(debit)
        has_credit = _is_present(credit)

        if has_debit == has_credit:
            issue_counts["invalid_amount_sides"] += 1

        for value in (debit, credit):
            if _is_present(value):
                amount = value if isinstance(value, Decimal) else Decimal(str(value))
                if amount < ZERO:
                    issue_counts["negative_amount"] += 1

    total_issues = sum(issue_counts.values())
    if total_issues == 0:
        return {
            "source_file": "ALL",
            "check": "transaction_integrity",
            "status": "PASS",
            "detail": f"All {len(frame)} normalized transactions passed structural checks.",
            "difference": None,
        }

    parts = [f"{name}={count}" for name, count in issue_counts.items() if count]
    return {
        "source_file": "ALL",
        "check": "transaction_integrity",
        "status": "FAIL",
        "detail": "Normalized transaction integrity failed: " + ", ".join(parts),
        "difference": None,
    }


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
