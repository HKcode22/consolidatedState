# ConsolidatedState — Bank Statement Consolidator

A small family-use web app that combines up to 12 monthly bank-statement PDFs into one validated Excel report.

## Goal

Dad opens one webpage, uploads the monthly statements, reviews any warnings, and downloads one consolidated workbook.

```text
1–12 PDF statements
        ↓
PDF inspection + text extraction
        ↓
Bank-specific parser
        ↓
Normalized transactions
        ↓
Validation / reconciliation
        ↓
Preview
        ↓
Consolidated Excel workbook
```

## MVP stack

- **UI + app server:** Streamlit / Python
- **PDF text extraction:** PyMuPDF
- **Data processing:** pandas
- **Excel output:** openpyxl
- **Tests:** pytest
- **Source of truth:** GitHub
- **Deployment target:** Replit

A separate React frontend, API server, Firebase database, and authentication system are intentionally avoided for v1. They would add complexity without improving the core consolidation task.

## Safety rule

Financial arithmetic must be deterministic. The application must never guess a missing dollar amount, silently change a transaction, or guess whether an ambiguous amount is money-in or money-out. If a statement layout is not recognized or does not reconcile, it is marked **Needs Review**.

## Current scope

The first working version targets **one known bank statement layout**. Supporting every bank automatically is out of scope for this short MVP.

Until representative statements are available, the app can safely validate PDFs, detect duplicate files, determine whether text is extractable, and exercise the normalization/validation/export pipeline using synthetic test data. The bank-specific transaction parser is added only after the real layout is inspected.

## Output workbook

The final `.xlsx` report will contain:

- `Transactions` — all normalized transactions in chronological order
- `Monthly Summary` — debit, credit, and net totals by month
- `Validation` — file-level and reconciliation results
- `About` — report disclaimer and generation notes

The output is a **consolidated report derived from bank statements**, not an official bank-issued statement.

## Privacy

This repository is currently public. **Never commit real bank statements, account/routing numbers, extracted statement text, or generated reports.**

Uploaded PDFs are intended to be processed in memory and not permanently stored by the application. Real deployment should be treated as private/family-use, and sample statements should be redacted where possible.

## What I need next

2–3 representative statements from the same bank, preferably with account/routing numbers redacted. From those samples we will identify the transaction table, statement period, opening/closing balance fields, and whether OCR is needed.
