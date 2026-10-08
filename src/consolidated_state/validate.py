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


def _account_groups(
    statements: list[StatementSummary],
) -> list[list[StatementSummary]]:
    groups: dict[str, list[StatementSummary]] = {}

    for index, statement in enumerate(statements):
        if statement.account_fingerprint:
            key = f"known:{statement.account_fingerprint}"
        else:
            key = f"unknown:{index}:{statement.source_file}"

        groups.setdefault(key, []).append(statement)

    return list(groups.values())


def validate_statement_set(statements: list[StatementSummary]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    if not statements:
        return rows

    known_accounts = {
        statement.account_fingerprint
        for statement in statements
        if statement.account_fingerprint
    }
    if len(known_accounts) > 1:
        rows.append({
            "source_file": "ALL",
            "check": "account_consistency",
            "status": "WARNING",
            "detail": (
                "Multiple account identities were detected. Multi-account consolidation "
                "is allowed; overlap, gap, and balance-continuity checks are performed "
                "only within the same detected account."
            ),
            "difference": None,
        })
    elif len(known_accounts) == 1 and all(statement.account_fingerprint for statement in statements):
        rows.append({
            "source_file": "ALL",
            "check": "account_consistency",
            "status": "PASS",
            "detail": "All statements with detected account identifiers belong to the same account.",
            "difference": None,
        })
    else:
        rows.append({
            "source_file": "ALL",
            "check": "account_consistency",
            "status": "WARNING",
            "detail": (
                "One or more statements did not expose a usable account identifier. "
                "Those statements are not assumed to belong to another statement's account."
            ),
            "difference": None,
        })

    known_currencies = {
        statement.currency
        for statement in statements
        if statement.currency
    }
    missing_currency_count = sum(
        1 for statement in statements if not statement.currency
    )

    if len(known_currencies) == 1 and missing_currency_count == 0:
        currency = next(iter(known_currencies))
        rows.append({
            "source_file": "ALL",
            "check": "currency_consistency",
            "status": "PASS",
            "detail": f"All statements explicitly identify currency {currency}.",
            "difference": None,
        })
    elif len(known_currencies) > 1:
        rows.append({
            "source_file": "ALL",
            "check": "currency_consistency",
            "status": "WARNING",
            "detail": (
                "Multiple explicit currencies were detected. Amounts are kept in separate "
                "currency groups and are never added together or converted."
            ),
            "difference": None,
        })
    else:
        rows.append({
            "source_file": "ALL",
            "check": "currency_consistency",
            "status": "WARNING",
            "detail": (
                "Currency was not explicitly identifiable on every statement. Unknown-currency "
                "statements are kept separate by source and are not combined with known-currency totals."
            ),
            "difference": None,
        })

    dated = [
        statement
        for statement in statements
        if statement.statement_start and statement.statement_end
    ]
    if len(dated) < len(statements):
        rows.append({
            "source_file": "ALL",
            "check": "statement_period_coverage",
            "status": "WARNING",
            "detail": "One or more exact statement periods could not be detected; coverage continuity is only partially verified.",
            "difference": None,
        })

    comparable_groups = [
        group
        for group in _account_groups(dated)
        if len(group) >= 2
    ]

    if not comparable_groups:
        if len(dated) >= 2:
            detail = (
                "No detected account group contains two or more dated statements, so "
                "cross-statement period and balance continuity are not compared across accounts."
            )
            for check in (
                "statement_period_overlap",
                "statement_period_gaps",
                "balance_continuity",
            ):
                rows.append({
                    "source_file": "ALL",
                    "check": check,
                    "status": "SKIPPED",
                    "detail": detail,
                    "difference": None,
                })
        return rows

    overlap_files: list[str] = []
    gap_messages: list[str] = []
    continuity_failures: list[str] = []

    for group in comparable_groups:
        ordered = sorted(group, key=lambda statement: statement.statement_start)

        for previous, current in zip(ordered, ordered[1:]):
            assert previous.statement_end is not None
            assert current.statement_start is not None

            if current.statement_start <= previous.statement_end:
                overlap_files.append(f"{previous.source_file} ↔ {current.source_file}")
                continue

            gap_days = (current.statement_start - previous.statement_end).days - 1
            if gap_days > 0:
                gap_messages.append(
                    f"{previous.source_file} → {current.source_file}: {gap_days} uncovered day(s)"
                )

            if (
                gap_days == 0
                and previous.closing_balance is not None
                and current.opening_balance is not None
                and abs(previous.closing_balance - current.opening_balance) > CENT
            ):
                continuity_failures.append(
                    f"{previous.source_file} closing balance does not match "
                    f"{current.source_file} opening balance"
                )

    if overlap_files:
        rows.append({
            "source_file": "ALL",
            "check": "statement_period_overlap",
            "status": "NEEDS_REVIEW",
            "detail": "Overlapping periods within the same detected account: " + "; ".join(overlap_files),
            "difference": None,
        })
    else:
        rows.append({
            "source_file": "ALL",
            "check": "statement_period_overlap",
            "status": "PASS",
            "detail": "No overlapping statement periods were detected within the same account.",
            "difference": None,
        })

    if gap_messages:
        rows.append({
            "source_file": "ALL",
            "check": "statement_period_gaps",
            "status": "WARNING",
            "detail": "Statement-period gaps within the same account: " + "; ".join(gap_messages),
            "difference": None,
        })
    else:
        rows.append({
            "source_file": "ALL",
            "check": "statement_period_gaps",
            "status": "PASS",
            "detail": "Detected statement periods are contiguous within each comparable account.",
            "difference": None,
        })

    if continuity_failures:
        rows.append({
            "source_file": "ALL",
            "check": "balance_continuity",
            "status": "FAIL",
            "detail": "; ".join(continuity_failures),
            "difference": None,
        })
    else:
        rows.append({
            "source_file": "ALL",
            "check": "balance_continuity",
            "status": "PASS",
            "detail": "Adjacent statements within each comparable account have consistent balances when available.",
            "difference": None,
        })

    return rows


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
