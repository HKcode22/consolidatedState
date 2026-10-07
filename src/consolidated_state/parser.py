from __future__ import annotations

from typing import Protocol

from .generic_parsers import (
    GenericParseError,
    LedgerColumnsStrategy,
    SectionedAmountStrategy,
)
from .layout import DocumentLayout, extract_document_layout
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
            return parser.parse(layout, source_file)
        except GenericParseError as exc:
            raise UnsupportedStatementFormat(str(exc)) from exc

    raise UnsupportedStatementFormat(
        "No verified generic layout strategy matches this statement yet. "
        "The document was left unparsed rather than guessing financial data."
    )
