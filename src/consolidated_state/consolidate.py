from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

import pandas as pd

from .models import StatementSummary, Transaction

TRANSACTION_COLUMNS = [
    "date",
    "description",
    "debit",
    "credit",
    "balance",
    "currency",
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
            "currency": tx.currency,
            "source_file": tx.source_file,
            "statement_period": tx.statement_period,
        }
        for tx in transactions
    ]
    frame = pd.DataFrame(rows, columns=TRANSACTION_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(["date", "source_file"], kind="stable").reset_index(drop=True)
    return frame


def find_duplicate_transactions(
    frame: pd.DataFrame,
    statements: Iterable[StatementSummary] | None = None,
) -> pd.DataFrame:
    """Return likely overlap duplicates only within the same detected account.

    Exact duplicate PDF uploads are handled separately by SHA-256. Identical-looking
    transactions from different detected accounts are not treated as duplicates.
    """
    if frame.empty:
        return frame.copy()

    key = ["date", "description", "debit", "credit", "balance"]
    candidates = frame[frame.duplicated(key, keep=False)].copy()

    if candidates.empty:
        return candidates

    if statements is None:
        keep_indexes: list[int] = []
        for _, group in candidates.groupby(key, dropna=False, sort=False):
            if group["source_file"].nunique(dropna=False) > 1:
                keep_indexes.extend(group.index.tolist())
        return (
            candidates.loc[keep_indexes].copy()
            if keep_indexes
            else candidates.iloc[0:0].copy()
        )

    source_to_account = {
        statement.source_file: statement.account_fingerprint
        for statement in statements
    }

    keep_indexes: list[int] = []
    for _, group in candidates.groupby(key, dropna=False, sort=False):
        sources = list(group["source_file"].dropna().unique())
        account_sources: dict[str, list[str]] = {}

        for source in sources:
            fingerprint = source_to_account.get(source)
            if fingerprint:
                account_sources.setdefault(fingerprint, []).append(source)

        eligible_sources = {
            source
            for grouped_sources in account_sources.values()
            if len(grouped_sources) > 1
            for source in grouped_sources
        }

        if eligible_sources:
            keep_indexes.extend(
                group[group["source_file"].isin(eligible_sources)].index.tolist()
            )

    return (
        candidates.loc[keep_indexes].copy()
        if keep_indexes
        else candidates.iloc[0:0].copy()
    )


def _money_or_zero(value: object) -> Decimal:
    if value is None or pd.isna(value):
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _currency_bucket(row: pd.Series) -> str:
    value = row.get("currency")
    if value is not None and not pd.isna(value) and str(value).strip():
        return str(value).strip().upper()

    source = str(row.get("source_file") or "unknown source")
    return f"Unknown ({source})"


def currency_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "currency",
        "source_statements",
        "transactions",
        "total_debits",
        "total_credits",
        "net",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    work = frame.copy()
    work["currency"] = work.apply(_currency_bucket, axis=1)
    work["debit"] = work["debit"].map(_money_or_zero)
    work["credit"] = work["credit"].map(_money_or_zero)

    summary = (
        work.groupby("currency", as_index=False, sort=True)
        .agg(
            source_statements=("source_file", "nunique"),
            transactions=("source_file", "size"),
            total_debits=("debit", "sum"),
            total_credits=("credit", "sum"),
        )
    )
    summary["net"] = summary["total_credits"] - summary["total_debits"]
    return summary[columns]


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["currency", "month", "total_debits", "total_credits", "net"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["month"] = work["date"].dt.to_period("M").astype(str)
    work["currency"] = work.apply(_currency_bucket, axis=1)
    work["debit"] = work["debit"].map(_money_or_zero)
    work["credit"] = work["credit"].map(_money_or_zero)

    summary = (
        work.groupby(["currency", "month"], as_index=False, sort=True)
        .agg(
            total_debits=("debit", "sum"),
            total_credits=("credit", "sum"),
        )
    )
    summary["net"] = summary["total_credits"] - summary["total_debits"]
    return summary[columns]
