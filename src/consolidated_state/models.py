from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Transaction:
    date: date
    description: str
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal | None = None
    source_file: str = ""
    statement_period: str = ""
    currency: str | None = None


@dataclass(frozen=True)
class StatementSummary:
    source_file: str
    statement_period: str = ""
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    statement_start: date | None = None
    statement_end: date | None = None
    account_fingerprint: str | None = None
    currency: str | None = None
    layout_strategy: str = ""


@dataclass(frozen=True)
class ParseResult:
    transactions: list[Transaction]
    statement: StatementSummary
    parser_name: str


@dataclass(frozen=True)
class PdfInspection:
    source_file: str
    sha256: str
    size_bytes: int
    page_count: int
    encrypted: bool
    has_text: bool
    status: str
    detail: str
