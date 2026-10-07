# Bank Statement Consolidator

A small family-use Streamlit app for inspecting up to 12 bank-statement PDFs and,
once one bank's layout is confirmed, consolidating transactions into Excel.

## Run

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 5000
```

## Privacy and current scope

- Uploaded PDFs and extracted text are processed in memory and are not written to
  disk, a database, or object storage.
- This app does not send statements to an LLM or external extraction API.
- The current shell checks PDF readability and duplicate files. It does not yet
  parse transactions; a bank-specific parser requires representative statements.
- OCR is not enabled. Do not publish the app for family use until access is
  restricted.

## Excel output

`workbook.py` generates an in-memory workbook with `Transactions`, `Monthly Summary`,
and `Validation` sheets for use once the bank parser is configured.
