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

    @property
    def net(self) -> Decimal:
        return (self.credit or Decimal("0")) - (self.debit or Decimal("0"))


@dataclass(frozen=True)
class StatementSummary:
    source_file: str
    statement_period: str = ""
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None


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
