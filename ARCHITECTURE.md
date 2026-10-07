# Architecture

## Core decision

Use a bank-agnostic, strategy-based parser.

```text
Browser
  |
  v
Streamlit app
  |
  +-- PDF preflight
  |     +-- duplicate?
  |     +-- encrypted?
  |     +-- embedded text?
  |     +-- OCR required?
  |
  +-- coordinate-aware PDF layout extraction
  |
  +-- strategy detector
  |     +-- running ledger
  |     +-- sectioned activity
  |     +-- future layout families
  |
  +-- normalized transactions
  |
  +-- deterministic validation/reconciliation
  |
  +-- monthly consolidation
  |
  `-- Excel export
```

## The parser is not selected by bank name

A statement from any bank can use a familiar structural family. The parser registry therefore answers:

> What kind of table is this?

rather than:

> Which bank made this?

This is what lets new banks work automatically when their layout matches an existing strategy.

## Why PDF coordinates matter

Plain extracted text often loses table relationships. A PDF may return all dates first, then all amounts, even though the page visually contains rows.

PyMuPDF exposes each word with its x/y coordinates. The parser can therefore reconstruct:

- row alignment;
- debit/credit/balance columns;
- right-aligned amount columns;
- continuation descriptions;
- repeated table headers.

This is much safer than trying to infer transaction rows from a flat text string.

## Generic strategy interface

Each strategy has two responsibilities:

1. `matches(layout)` — determine whether the structural family is present.
2. `parse(layout)` — create normalized transactions.

Strategies never decide whether the final report is trustworthy. The validation layer does that independently.

## Validation boundary

A successful parse is necessary but not sufficient.

Before export:

- every uploaded file must parse;
- normalized transaction rows must pass structural checks;
- potential duplicates must be reviewed;
- opening/closing balances must reconcile when available.

Any blocking condition prevents export.

## Expansion path

New statement examples are first tested against existing strategies. Only genuinely new structural families add parser code.

This keeps the project extensible without a bank-by-bank hardcoded design.

## OCR

Image-only PDFs are a separate extraction problem. The current preflight detects them and blocks export. A future free OCR stage can feed recognized words/coordinates into the same strategy architecture.

## LLM decision

An LLM is intentionally not part of the financial extraction path. Exact amounts and debit/credit direction are determined from document structure and verified mathematically. An LLM could be added later for optional description categorization, but not as the authority for financial values.
