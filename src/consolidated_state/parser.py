from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from .generic_parsers import (
    GenericParseError,
    LedgerColumnsStrategy,
    SectionedAmountStrategy,
)
from .layout import DocumentLayout, extract_document_layout
from .metadata import extract_statement_metadata
from .models import ParseResult


class UnsupportedStatementFormat(ValueError):
    """Raised when no verified generic layout strategy recognizes a statement."""


class ParserStrategy(Protocol):
    name: str

    def matches(self, layout: DocumentLayout) -> bool: ...

    def parse(self, layout: DocumentLayout, source_file: str) -> ParseResult: ...


PARSERS: list[ParserStrategy] = [
    LedgerColumnsStrategy(),
    SectionedAmountStrategy(),
]


def _enrich_result(result: ParseResult, layout: DocumentLayout) -> ParseResult:
    metadata = extract_statement_metadata(layout)

    if metadata.statement_start and metadata.statement_end:
        period = (
            f"{metadata.statement_start.isoformat()} to "
            f"{metadata.statement_end.isoformat()}"
        )
    else:
        period = result.statement.statement_period

    statement = replace(
        result.statement,
        statement_period=period,
        statement_start=metadata.statement_start,
        statement_end=metadata.statement_end,
        account_fingerprint=metadata.account_fingerprint,
        currency=metadata.currency,
        layout_strategy=result.parser_name,
    )

    transactions = [
        replace(transaction, statement_period=period)
        for transaction in result.transactions
    ]

    return ParseResult(
        transactions=transactions,
        statement=statement,
        parser_name=result.parser_name,
    )


def parse_statement(
    text: str,
    source_file: str,
    pdf_bytes: bytes | None = None,
) -> ParseResult:
    del text  # Layout strategies intentionally rely on PDF geometry, not bank names.

    if not pdf_bytes:
        raise UnsupportedStatementFormat(
            "Layout-aware parsing requires the source PDF bytes. "
            "No financial data was guessed."
        )

    layout = extract_document_layout(pdf_bytes)

    for parser in PARSERS:
        if not parser.matches(layout):
            continue

        try:
            return _enrich_result(
                parser.parse(layout, source_file),
                layout,
            )
        except GenericParseError as exc:
            raise UnsupportedStatementFormat(str(exc)) from exc

    raise UnsupportedStatementFormat(
        "No verified generic layout strategy matches this statement yet. "
        "The document was left unparsed rather than guessing financial data."
    )
