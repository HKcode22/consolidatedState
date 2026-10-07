# Architecture

## Decision

Use one Streamlit application for the MVP.

```text
Browser
  |
  | HTTPS
  v
Streamlit app on Replit
  |-- upload + review UI
  |-- PDF inspection/extraction
  |-- bank parser adapter
  |-- normalization
  |-- validation/reconciliation
  `-- Excel generation
```

There is no database in v1 and no need for a separate React frontend or REST API.

## Internal modules

- `app.py` — user workflow only
- `pdf_inspect.py` — PDF validation, hashing, text extraction
- `models.py` — typed statement/transaction records
- `parser.py` — parser interface and supported-bank adapters
- `consolidate.py` — dataframe normalization and summaries
- `validate.py` — duplicate and reconciliation checks
- `export_excel.py` — deterministic workbook generation

## Trust boundaries

PDF bytes enter through the upload widget and should remain in memory. The application should not log statement text, account numbers, transaction descriptions, or balances. GitHub contains code only. Replit contains runtime code/configuration only.

## Why not Firebase for v1?

Firebase would require us to design a frontend/backend split and potentially a persistence/auth layer that the consolidation problem does not need. Streamlit gives us the upload UI and Python execution in one app, which minimizes code and failure points.

## Why not AI-first extraction?

A bank statement is structured financial data. Exact amounts and arithmetic should be parsed and validated deterministically. AI can be considered later for layout mapping or description categorization, but it should not be trusted as the source of financial values.
