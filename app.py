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
from consolidated_state.readiness import export_is_safe
from consolidated_state.validate import reconcile_statement, validate_statement_set, validate_transaction_rows

st.set_page_config(page_title="ConsolidatedState", page_icon="📄", layout="wide")

st.title("Bank Statement Consolidator")
st.caption("Upload monthly statements, validate them, and create one consolidated Excel report.")
st.info(
    "Privacy: this app does not intentionally save uploaded statement files. "
    "Financial rows are extracted by verified generic layout strategies; unknown layouts are never guessed."
)

uploaded_files = st.file_uploader(
    "Upload 1–12 bank statement PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="Statements may come from different banks/layouts, but one consolidation should represent the same account and currency.",
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
    parsed_files: set[str] = set()

    for uploaded in uploaded_files:
        pdf_bytes = uploaded.getvalue()
        inspection, text = inspect_and_extract_pdf(pdf_bytes, uploaded.name)

        duplicate_of = seen_hashes.get(inspection.sha256)
        if duplicate_of is None:
            seen_hashes[inspection.sha256] = uploaded.name

        intake_status = "DUPLICATE_FILE" if duplicate_of else inspection.status
        intake_detail = f"Exact duplicate of {duplicate_of}." if duplicate_of else inspection.detail

        inspections.append(
            {
                "source_file": inspection.source_file,
                "pages": inspection.page_count,
                "size_mb": round(inspection.size_bytes / (1024 * 1024), 2),
                "embedded_text": inspection.has_text,
                "status": intake_status,
                "detail": intake_detail,
            }
        )

        validation_rows.append(
            {
                "source_file": uploaded.name,
                "check": "pdf_intake",
                "status": "PASS" if intake_status == "TEXT_READY" else intake_status,
                "detail": intake_detail,
                "difference": None,
            }
        )

        if duplicate_of or inspection.status != "TEXT_READY":
            continue

        try:
            parsed = parse_statement(text, uploaded.name, pdf_bytes=pdf_bytes)
            all_transactions.extend(parsed.transactions)
            statement_summaries.append(parsed.statement)
            parsed_files.add(uploaded.name)
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
                    "status": "NEEDS_LAYOUT_STRATEGY",
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
            "The PDF intake layer is working, but none of the current generic layout strategies safely parsed these statement(s). "
            "A new structural strategy can be added without hardcoding the bank name."
        )
        st.subheader("2. Validation")
        st.dataframe(pd.DataFrame(validation_rows), use_container_width=True, hide_index=True)
        st.stop()

    validation_rows.append(validate_transaction_rows(transaction_frame))
    validation_rows.extend(validate_statement_set(statement_summaries))

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

    safe_to_export, blocking_reasons = export_is_safe(
        validation_frame,
        uploaded_file_count=len(uploaded_files),
        parsed_file_count=len(parsed_files),
    )

    if not safe_to_export:
        st.error("Export blocked. Every uploaded statement must pass validation before a consolidated report is created.")
        with st.expander("Why export is blocked"):
            for reason in blocking_reasons:
                st.write(f"- {reason}")
        st.stop()

    report = build_excel_report(transaction_frame, summary_frame, validation_frame, statement_summaries)
    st.success("All uploaded statements passed the current validation gates.")
    st.download_button(
        "Download consolidated Excel report",
        data=report,
        file_name="consolidated_bank_statement_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
