from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .models import StatementSummary


def sum_money(series: pd.Series) -> Decimal:
    total = Decimal("0.00")
    for value in series:
        if value is None or pd.isna(value):
            continue
        total += value if isinstance(value, Decimal) else Decimal(str(value))
    return total


def build_overview_frame(
    transactions: pd.DataFrame,
    statements: list[StatementSummary],
) -> pd.DataFrame:
    credits = (
        transactions[transactions["credit"].notna()]
        if not transactions.empty
        else transactions
    )
    debits = (
        transactions[transactions["debit"].notna()]
        if not transactions.empty
        else transactions
    )

    total_credits = (
        sum_money(credits["credit"])
        if not credits.empty
        else Decimal("0.00")
    )
    total_debits = (
        sum_money(debits["debit"])
        if not debits.empty
        else Decimal("0.00")
    )

    dated_statements = [
        statement
        for statement in statements
        if statement.statement_start and statement.statement_end
    ]

    if dated_statements:
        covered_period = (
            f"{min(statement.statement_start for statement in dated_statements).isoformat()} to "
            f"{max(statement.statement_end for statement in dated_statements).isoformat()}"
        )
    elif transactions.empty:
        covered_period = ""
    else:
        dates = pd.to_datetime(transactions["date"])
        covered_period = (
            f"{dates.min().date().isoformat()} to "
            f"{dates.max().date().isoformat()}"
        )

    currencies = {
        statement.currency
        for statement in statements
        if statement.currency
    }

    if len(currencies) == 1:
        currency = next(iter(currencies))
    elif len(currencies) > 1:
        currency = "MIXED"
    else:
        currency = "Not explicitly identified"

    ordered_statements = sorted(
        statements,
        key=lambda statement: statement.statement_period or "9999",
    )

    opening = next(
        (
            statement.opening_balance
            for statement in ordered_statements
            if statement.opening_balance is not None
        ),
        None,
    )

    closing = next(
        (
            statement.closing_balance
            for statement in reversed(ordered_statements)
            if statement.closing_balance is not None
        ),
        None,
    )

    rows = [
        ("Covered period", covered_period),
        ("Currency", currency),
        ("Source statements", len(statements)),
        ("Total transactions", len(transactions)),
        ("Deposits / additions count", len(credits)),
        ("Deposits / additions total", total_credits),
        ("Withdrawals / subtractions count", len(debits)),
        ("Withdrawals / subtractions total", total_debits),
        ("Net change", total_credits - total_debits),
        ("Beginning balance", opening),
        ("Ending balance", closing),
    ]

    return pd.DataFrame(rows, columns=["Metric", "Value"])


def build_statement_frame(
    statements: list[StatementSummary],
) -> pd.DataFrame:
    rows = [
        {
            "source_file": statement.source_file,
            "statement_period": statement.statement_period,
            "currency": statement.currency or "Not explicitly identified",
            "account_identifier_detected": bool(statement.account_fingerprint),
            "opening_balance": statement.opening_balance,
            "closing_balance": statement.closing_balance,
            "layout_strategy": statement.layout_strategy,
        }
        for statement in statements
    ]

    return pd.DataFrame(
        rows,
        columns=[
            "source_file",
            "statement_period",
            "currency",
            "account_identifier_detected",
            "opening_balance",
            "closing_balance",
            "layout_strategy",
        ],
    )
