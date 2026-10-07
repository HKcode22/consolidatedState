# MVP Build Plan

## Target

A small, reliable family-use web app. The first usable version should be achievable in a short build session once sample statements are available.

## Definition of done

1. Dad opens the web app.
2. Uploads 1–12 PDF statements from the supported bank.
3. The app rejects unreadable/duplicate/unsupported files instead of guessing.
4. Transactions are normalized into date, description, debit, credit, balance, source file, and statement period.
5. Validation checks run before export.
6. Dad previews the result and downloads one Excel workbook.

## Phase 1 — Clean foundation

- GitHub is the source of truth.
- Replit is the runtime/deployment environment.
- Single Python/Streamlit app; no separate frontend/backend for v1.
- Add `.gitignore` protections for PDFs, spreadsheets, secrets, and generated output.
- Add automated synthetic tests.

## Phase 2 — Safe PDF intake

- Upload 1–12 PDFs.
- Enforce file count and reasonable size limits.
- Compute SHA-256 hashes in memory to detect identical duplicate uploads.
- Detect encrypted/password-protected PDFs.
- Count pages and determine whether embedded text exists.
- Do not persist PDF contents.

## Phase 3 — Learn one real bank format

Requires 2–3 representative statements.

- Identify statement period and year.
- Identify opening and closing balances.
- Identify transaction row structure.
- Determine debit/credit/balance semantics.
- Determine whether multi-line descriptions occur.
- Determine whether scanned PDFs require OCR.

## Phase 4 — Bank-specific parser

- Parse only a recognized layout.
- Normalize fields into a single transaction schema.
- Preserve source filename and statement period for traceability.
- Reject ambiguous rows; never infer financial values silently.

## Phase 5 — Validation and reconciliation

- Exact duplicate file detection.
- Duplicate/overlapping transaction detection.
- Statement-period ordering and missing-period warnings.
- Opening + credits - debits ≈ closing balance when the source statement exposes those values.
- Flag parsing/reconciliation failures before export.

## Phase 6 — Consolidation and export

- Combine transactions chronologically.
- Create monthly totals.
- Preview transactions and warnings in the web app.
- Generate one `.xlsx` file with Transactions, Monthly Summary, Validation, and About sheets.

## Phase 7 — Handoff

- Run end-to-end tests with redacted copies.
- Deploy on Replit.
- Dad uses one URL: Upload → Process → Review → Download.

## Not in the 2–4 hour MVP

- Universal support for arbitrary banks.
- Training a custom AI/ML model.
- LLM calls containing real financial statements.
- User accounts or a database.
- Permanent statement storage.
- Reproducing an official bank statement design.

## Later enhancements

Only if useful after v1 works:

- Multiple bank adapters.
- OCR for scanned statements.
- Optional merchant/category classification.
- Password/family-only access.
- PDF summary report in addition to Excel.
