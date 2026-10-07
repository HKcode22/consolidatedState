from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import StatementSummary, Transaction


class UnsupportedStatementFormat(ValueError):
    """Raised when no verified parser recognizes a statement layout."""


@dataclass(frozen=True)
class ParseResult:
    transactions: list[Transaction]
    statement: StatementSummary
    parser_name: str


class ParserAdapter(Protocol):
    name: str

    def matches(self, text: str) -> bool: ...

    def parse(self, text: str, source_file: str) -> ParseResult: ...


# Verified bank adapters are added here only after representative statements are reviewed.
PARSERS: list[ParserAdapter] = []


def parse_statement(text: str, source_file: str) -> ParseResult:
    for parser in PARSERS:
        if parser.matches(text):
            return parser.parse(text, source_file)
    raise UnsupportedStatementFormat(
        "No verified bank-specific parser matches this statement yet. "
        "Provide representative statement samples before financial rows are extracted."
    )
