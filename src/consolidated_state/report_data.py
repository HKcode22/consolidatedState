from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .consolidate import currency_summary
from .models import StatementSummary


def sum_money(series: pd.Series) -> Decimal:
    total = Decimal("0.00")
    for value in series:
        if value is None or pd.isna(value):
            continue
        total += value if isinstance(value, Decimal) else Decimal(str(value))
    return total


def _account_label_map(
    statements: list[StatementSummary],
) -> dict[str, str]:
    labels: dict[str, str] = {}
    next_number = 1

    for statement in statements:
        fingerprint = statement.account_fingerprint
        if not fingerprint or fingerprint in labels:
            continue

        labels[fingerprint] = f"Account {next_number}"
        next_number += 1

    return labels


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

    money_summary = currency_summary(transactions)
    if len(money_summary) == 1:
        money_row = money_summary.iloc[0]
        currency = str(money_row["currency"])
        total_credits: object = money_row["total_credits"]
        total_debits: object = money_row["total_debits"]
        net_change: object = money_row["net"]
    elif len(money_summary) > 1:
        currency = "Multiple / separated"
        total_credits = "See Currency Summary"
        total_debits = "See Currency Summary"
        net_change = "See Currency Summary"
    else:
        currency = "Not available"
        total_credits = Decimal("0.00")
        total_debits = Decimal("0.00")
        net_change = Decimal("0.00")

    known_accounts = {
        statement.account_fingerprint
        for statement in statements
        if statement.account_fingerprint
    }
    unknown_account_count = sum(
        1 for statement in statements if not statement.account_fingerprint
    )
    account_groups = len(known_accounts) + unknown_account_count

    one_verified_account = (
        len(known_accounts) == 1
        and unknown_account_count == 0
    )

    if one_verified_account:
        ordered_statements = sorted(
            statements,
            key=lambda statement: statement.statement_period or "9999",
        )
        opening: object = next(
            (
                statement.opening_balance
                for statement in ordered_statements
                if statement.opening_balance is not None
            ),
            None,
        )
        closing: object = next(
            (
                statement.closing_balance
                for statement in reversed(ordered_statements)
                if statement.closing_balance is not None
            ),
            None,
        )
    elif len(statements) == 1:
        opening = statements[0].opening_balance
        closing = statements[0].closing_balance
    else:
        opening = "See Source Statements"
        closing = "See Source Statements"

    rows = [
        ("Covered period", covered_period),
        ("Currency handling", currency),
        ("Source statements", len(statements)),
        ("Detected account groups", account_groups),
        ("Total transactions", len(transactions)),
        ("Deposits / additions count", len(credits)),
        ("Deposits / additions total", total_credits),
        ("Withdrawals / subtractions count", len(debits)),
        ("Withdrawals / subtractions total", total_debits),
        ("Net change", net_change),
        ("Beginning balance", opening),
        ("Ending balance", closing),
    ]

    return pd.DataFrame(rows, columns=["Metric", "Value"])


def build_statement_frame(
    statements: list[StatementSummary],
) -> pd.DataFrame:
    account_labels = _account_label_map(statements)

    rows = [
        {
            "source_file": statement.source_file,
            "account_group": (
                account_labels.get(statement.account_fingerprint, "Not identified")
                if statement.account_fingerprint
                else "Not identified"
            ),
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
            "account_group",
            "statement_period",
            "currency",
            "account_identifier_detected",
            "opening_balance",
            "closing_balance",
            "layout_strategy",
        ],
    )
