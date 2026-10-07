from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

import pandas as pd

from .models import Transaction

TRANSACTION_COLUMNS = [
    "date",
    "description",
    "debit",
    "credit",
    "balance",
    "source_file",
    "statement_period",
]

ZERO = Decimal("0.00")


def transactions_to_frame(transactions: Iterable[Transaction]) -> pd.DataFrame:
    rows = [
        {
            "date": tx.date,
            "description": tx.description,
            "debit": tx.debit,
            "credit": tx.credit,
            "balance": tx.balance,
            "source_file": tx.source_file,
            "statement_period": tx.statement_period,
        }
        for tx in transactions
    ]
    frame = pd.DataFrame(rows, columns=TRANSACTION_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(["date", "source_file"], kind="stable").reset_index(drop=True)
    return frame


def find_duplicate_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    key = ["date", "description", "debit", "credit"]
    return frame[frame.duplicated(key, keep=False)].copy()


def _money_or_zero(value: object) -> Decimal:
    if value is None or pd.isna(value):
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["month", "total_debits", "total_credits", "net"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["month"] = work["date"].dt.to_period("M").astype(str)
    work["debit"] = work["debit"].map(_money_or_zero)
    work["credit"] = work["credit"].map(_money_or_zero)

    summary = (
        work.groupby("month", as_index=False)
        .agg(total_debits=("debit", "sum"), total_credits=("credit", "sum"))
    )
    summary["net"] = summary["total_credits"] - summary["total_debits"]
    return summary[columns]
