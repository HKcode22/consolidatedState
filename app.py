from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256

import streamlit as st

from statement_processing import inspect_uploaded_files


MAX_STATEMENTS = 12

st.set_page_config(
    page_title="Bank Statement Consolidator",
    page_icon=None,
    layout="wide",
)

st.title("Bank Statement Consolidator")
st.write(
    "Bring up to 12 monthly statements together. This first step checks that the PDFs "
    "can be read and identifies duplicates before any transaction data is consolidated."
)

st.info(
    "Privacy: PDFs are inspected in memory on this app server. This version does not "
    "save statement files or extracted text to disk, a database, or an AI service. "
    "Do not publish the app for family use until access is restricted."
)

st.subheader("Upload statements")
uploaded_files = st.file_uploader(
    "Choose 1–12 PDF statements",
    type=["pdf"],
    accept_multiple_files=True,
    help="Select monthly statements from the same bank and account.",
)

file_count = len(uploaded_files or [])
if file_count > MAX_STATEMENTS:
    st.error(f"Choose no more than {MAX_STATEMENTS} PDFs at a time.")
elif file_count == 0:
    st.caption("No files are selected. You can select up to 12 PDF statements.")
else:
    st.caption(f"{file_count} of {MAX_STATEMENTS} PDFs selected.")

fingerprint = tuple(
    (file.name, sha256(file.getvalue()).hexdigest()) for file in (uploaded_files or [])
)
if st.session_state.get("inspection_fingerprint") != fingerprint:
    st.session_state.pop("inspection_results", None)
    st.session_state["inspection_fingerprint"] = fingerprint

if st.button(
    "Inspect statements",
    type="primary",
    disabled=not uploaded_files or file_count > MAX_STATEMENTS,
):
    reports = inspect_uploaded_files(uploaded_files or [])
    st.session_state["inspection_results"] = [asdict(report) for report in reports]

results = st.session_state.get("inspection_results")
if results:
    st.divider()
    st.subheader("Inspection results")

    readable_count = sum(report["status"] == "Text found" for report in results)
    duplicate_count = sum(report["status"] == "Duplicate" for report in results)
    issue_count = len(results) - readable_count - duplicate_count

    metric_columns = st.columns(3)
    metric_columns[0].metric("Statements", len(results))
    metric_columns[1].metric("With embedded text", readable_count)
    metric_columns[2].metric("Need attention", issue_count + duplicate_count)

    st.dataframe(
        [
            {
                "File": report["filename"],
                "Pages": report["page_count"] if report["page_count"] is not None else "—",
                "Text characters": report["text_characters"],
                "Status": report["status"],
                "Details": report["details"],
            }
            for report in results
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.warning(
        "The bank-specific transaction parser is not configured yet. No transaction "
        "rows are being guessed or merged. After the statement layout is confirmed, "
        "the app can add chronological transactions, validation checks, and the Excel export."
    )

    if duplicate_count:
        st.caption(
            "Duplicate files are listed for review and are not treated as additional months."
        )

st.divider()
with st.expander("What this version checks"):
    st.markdown(
        """
        - Whether each PDF can be opened and has extractable embedded text.
        - Whether two uploaded files have identical contents.
        - Whether a file is encrypted, unreadable, or likely image-only.

        This inspection does **not** determine transaction dates, amounts, statement
        periods, or balances. OCR is not enabled. Those checks will be added only after
        the first bank's statement layout is reviewed.
        """
    )
