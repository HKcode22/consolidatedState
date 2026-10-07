# Build Plan

## Target

A small, reliable web application that consolidates bank-statement transactions without being tied to one bank.

## Definition of done

1. User opens the web app.
2. Uploads 1–12 PDF statements intended for one consolidation.
3. The app inspects each PDF and determines whether text/layout data are available.
4. A generic structural parser recognizes the statement layout.
5. Transactions normalize to date, description, debit, credit, balance, source file, and statement period.
6. Validation runs before export.
7. Any failed/ambiguous statement blocks export.
8. User previews the result and downloads one consolidated workbook.

## Phase 1 — Foundation — COMPLETE

- GitHub is the source of truth.
- Replit is the runtime/deployment environment.
- Single Python/Streamlit application.
- Privacy-focused gitignore.
- Synthetic automated tests.

## Phase 2 — Safe PDF intake — COMPLETE

- 1–12 PDFs.
- 20 MB per-file limit.
- SHA-256 duplicate detection.
- Encrypted/password-protected PDF detection.
- Embedded-text vs OCR-required detection.
- In-memory processing.

## Phase 3 — Bank-agnostic layout engine — IN PROGRESS

The parser chooses a strategy from document structure rather than a bank name.

Initial layout families:

- two-sided running ledger: Date / Details / Debit/Credit (or Withdrawals/Deposits, Money Out/Money In) / Balance
- sectioned activity: Deposits/Credits and Withdrawals/Debits, each with Date / Description / Amount
- single-amount ledger: Date / Description / Amount / Balance, with direction proven by sign or balance movement

New examples are used to discover **new layout families**, not to hardcode bank brands.

## Phase 4 — Normalization and validation

- Exact Decimal arithmetic.
- Every row must have a date, description, source, and exactly one debit/credit side.
- Duplicate/overlapping transaction detection.
- Opening + credits - debits = closing balance where balances are available.
- Same-account compatibility checks using hashed account identifiers when detectable.
- Explicit-currency consistency checks; no currency conversion.
- Statement-period overlap/gap checks and adjacent balance continuity.
- International numeric-date order is inferred safely instead of assuming U.S. format.
- Fail-closed export: one failed input blocks the consolidated workbook.

## Phase 5 — Consolidation

- Combine transactions chronologically.
- Monthly debit/credit/net summaries.
- Preserve source file and statement period.
- Validation report accompanies output.

## Phase 6 — Broader format coverage

As new samples arrive:

1. run them through existing strategies;
2. if a strategy succeeds and reconciles, no new parser is needed;
3. if not, identify the structural difference;
4. add a new generic layout strategy plus synthetic regression tests.

Likely future strategy families:

- signed Amount + Balance ledgers;
- separate Money In / Money Out columns;
- multi-page tables with repeated headers;
- non-English heading dictionaries.

## Phase 7 — OCR

For scanned/image-only statements:

- detect OCR requirement automatically;
- add a free local OCR path;
- run the same layout/validation pipeline on OCR output;
- do not use an LLM to invent missing financial values.

## Phase 8 — Handoff

- end-to-end tests on representative redacted samples;
- restrict access appropriately;
- publish on Replit;
- user flow: Upload → Process → Review → Download.

## Important limitation

"Any bank" is a coverage goal, not an honest absolute guarantee. Arbitrary PDFs can contain unseen layouts, scans, malformed fonts, languages, and incomplete information.

The software therefore prefers:

**unsupported + review**

over:

**plausible-looking but incorrect financial output**.
