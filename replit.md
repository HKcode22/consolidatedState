# Bank Statement Consolidator

A family-use Streamlit app for inspecting up to 12 monthly bank-statement PDFs and, once one bank layout is confirmed, consolidating transactions into an Excel workbook.

## Run & Operate

- `streamlit run app.py --server.address 0.0.0.0 --server.port 5000` — run the app
- Python dependencies are declared in `pyproject.toml` and locked in `uv.lock`.
- No database or application secrets are required for local processing.

## Stack

- Python 3.11, Streamlit, pypdf, and openpyxl.
- The existing pnpm workspace scaffold remains available, but the bank-statement app runs as a Streamlit workflow.

## Where things live

- `app.py` — Streamlit upload and review interface.
- `statement_processing.py` — in-memory PDF inspection and duplicate detection.
- `workbook.py` — in-memory Excel workbook generation for the confirmed parser output.
- `pyproject.toml` / `uv.lock` — Python dependency source of truth.

## Architecture decisions

- PDF bytes and extracted text are processed in memory; do not add disk, database, or object-storage persistence.
- Do not send bank documents to an LLM or external extraction API.
- Build a parser only for the bank layout confirmed from representative statements; refuse uncertain rows rather than guessing.
- Do not add OCR unless the sample PDFs show that statements are scanned.

## Product

- Accept 1–12 PDF statements, identify duplicate files, and report whether embedded text is available.
- The first version will support one bank layout and export Transactions, Monthly Summary, and Validation worksheets after that layout is confirmed.
- Before publishing for family use, verify access restrictions; the initial app shell does not add sign-in.

## User preferences

- Keep this a small family-use app, not a multi-bank platform.
- Do not retain bank statements, use OCR preemptively, or make LLM/API calls with financial documents.

## Gotchas

- Text extraction is a format inspection step, not evidence that transaction rows were parsed correctly.
- Keep uploaded PDFs out of GitHub and out of sample/test fixtures.

## Pointers

- See `README.md` for the app run command and initial privacy/processing scope.
