from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from consolidated_state.consolidate import (
    find_duplicate_transactions,
    monthly_summary,
    transactions_to_frame,
)
from consolidated_state.export_excel import build_excel_report
from consolidated_state.parser import UnsupportedStatementFormat, parse_statement
from consolidated_state.pdf_inspect import inspect_and_extract_pdf
from consolidated_state.validate import reconcile_statement

st.set_page_config(page_title="ConsolidatedState", page_icon="📄", layout="wide")

st.title("Bank Statement Consolidator")
st.caption("Upload monthly statements, validate them, and create one consolidated Excel report.")
st.info(
    "Privacy: this app does not intentionally save uploaded statement files. "
    "Financial rows are extracted only by a verified bank-specific parser; unknown layouts are never guessed."
)

uploaded_files = st.file_uploader(
    "Upload 1–12 bank statement PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="For the first MVP, all statements should come from the same supported bank/account layout.",
)

if uploaded_files and len(uploaded_files) > 12:
    st.error("Please upload no more than 12 statements at once.")
    st.stop()

if uploaded_files and st.button("Inspect and consolidate", type="primary"):
    inspections: list[dict[str, object]] = []
    all_transactions = []
    statement_summaries = []
    validation_rows: list[dict[str, object]] = []
    seen_hashes: dict[str, str] = {}

    for uploaded in uploaded_files:
        pdf_bytes = uploaded.getvalue()
        inspection, text = inspect_and_extract_pdf(pdf_bytes, uploaded.name)

        duplicate_of = seen_hashes.get(inspection.sha256)
        if duplicate_of is None:
            seen_hashes[inspection.sha256] = uploaded.name

        row = {
            "source_file": inspection.source_file,
            "pages": inspection.page_count,
            "size_mb": round(inspection.size_bytes / (1024 * 1024), 2),
            "embedded_text": inspection.has_text,
            "status": "DUPLICATE_FILE" if duplicate_of else inspection.status,
            "detail": f"Exact duplicate of {duplicate_of}." if duplicate_of else inspection.detail,
        }
        inspections.append(row)

        if duplicate_of or inspection.status != "TEXT_READY":
            continue

        try:
            parsed = parse_statement(text, uploaded.name)
            all_transactions.extend(parsed.transactions)
            statement_summaries.append(parsed.statement)
            validation_rows.append(
                {
                    "source_file": uploaded.name,
                    "check": "parser",
                    "status": "PASS",
                    "detail": f"Parsed with {parsed.parser_name}.",
                    "difference": None,
                }
            )
        except UnsupportedStatementFormat as exc:
            validation_rows.append(
                {
                    "source_file": uploaded.name,
                    "check": "parser",
                    "status": "NEEDS_BANK_PARSER",
                    "detail": str(exc),
                    "difference": None,
                }
            )

    inspection_frame = pd.DataFrame(inspections)
    st.subheader("1. PDF intake")
    st.dataframe(inspection_frame, use_container_width=True, hide_index=True)

    transaction_frame = transactions_to_frame(all_transactions)
    if transaction_frame.empty:
        st.warning(
            "The PDF intake layer is working, but no verified bank parser is installed yet. "
            "Send 2–3 representative statements and we can implement the exact parser without guessing financial data."
        )
        if validation_rows:
            st.subheader("2. Parser status")
            st.dataframe(pd.DataFrame(validation_rows), use_container_width=True, hide_index=True)
        st.stop()

    duplicate_transactions = find_duplicate_transactions(transaction_frame)
    if not duplicate_transactions.empty:
        validation_rows.append(
            {
                "source_file": "ALL",
                "check": "duplicate_transactions",
                "status": "NEEDS_REVIEW",
                "detail": f"Found {len(duplicate_transactions)} rows participating in possible duplicates.",
                "difference": None,
            }
        )

    for statement in statement_summaries:
        validation_rows.append(reconcile_statement(statement, transaction_frame))

    validation_frame = pd.DataFrame(validation_rows)
    summary_frame = monthly_summary(transaction_frame)

    st.subheader("2. Validation")
    st.dataframe(validation_frame, use_container_width=True, hide_index=True)

    st.subheader("3. Consolidated transactions")
    st.dataframe(transaction_frame, use_container_width=True, hide_index=True)

    st.subheader("4. Monthly summary")
    st.dataframe(summary_frame, use_container_width=True, hide_index=True)

    has_failure = validation_frame["status"].isin(["FAIL", "NEEDS_REVIEW", "NEEDS_BANK_PARSER"]).any()
    if has_failure:
        st.warning("Review validation warnings before relying on the exported totals.")

    report = build_excel_report(transaction_frame, summary_frame, validation_frame)
    st.download_button(
        "Download consolidated Excel report",
        data=report,
        file_name="consolidated_bank_statement_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
