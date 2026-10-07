from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from consolidated_state.access import passcode_matches
from consolidated_state.pipeline import ConsolidationResult, process_statements

st.set_page_config(
    page_title="ConsolidatedState",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        .cs-hero {
            padding: 1.55rem 1.6rem;
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 18px;
            margin-bottom: 1.2rem;
        }
        .cs-hero h1 {
            margin: 0 0 0.35rem 0;
            font-size: 2.1rem;
        }
        .cs-hero p {
            margin: 0;
            opacity: 0.78;
            font-size: 1rem;
        }
        .cs-step {
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 14px;
            padding: 0.85rem 1rem;
            min-height: 92px;
        }
        .cs-step strong {
            display: block;
            margin-bottom: 0.25rem;
        }
        .cs-note {
            font-size: 0.9rem;
            opacity: 0.78;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def clear_previous_result() -> None:
    st.session_state.pop("consolidation_result", None)


def require_optional_passcode() -> None:
    configured = os.getenv("APP_PASSCODE", "").strip()
    if not configured:
        st.sidebar.warning(
            "Access passcode is not configured. Before publishing for real "
            "financial documents, add APP_PASSCODE in Replit Secrets."
        )
        return

    if st.session_state.get("authenticated") is True:
        st.sidebar.success("Family access unlocked")
        return

    st.markdown(
        """
        <div class="cs-hero">
            <h1>🔒 ConsolidatedState</h1>
            <p>This private tool requires the family access passcode.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    supplied = st.text_input(
        "Access passcode",
        type="password",
        key="access_passcode",
    )

    if st.button("Unlock", type="primary"):
        if passcode_matches(supplied, configured):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect passcode.")

    st.stop()


def money_text(value) -> str:
    return f"{value:,.2f}"


def detected_currency(result: ConsolidationResult) -> str:
    if result.statements.empty or "currency" not in result.statements:
        return ""

    values = {
        str(value)
        for value in result.statements["currency"].tolist()
        if value and value != "Not explicitly identified"
    }

    if len(values) == 1:
        return next(iter(values))

    if len(values) > 1:
        return "Mixed"

    return ""


def render_result(result: ConsolidationResult) -> None:
    st.divider()

    currency = detected_currency(result)
    suffix = f" {currency}" if currency and currency != "Mixed" else ""

    metric_columns = st.columns(5)
    metric_columns[0].metric(
        "Statements parsed",
        len(result.statements),
    )
    metric_columns[1].metric(
        "Transactions",
        len(result.transactions),
    )
    metric_columns[2].metric(
        "Deposits / credits",
        f"{money_text(result.total_credits)}{suffix}",
    )
    metric_columns[3].metric(
        "Withdrawals / debits",
        f"{money_text(result.total_debits)}{suffix}",
    )
    metric_columns[4].metric(
        "Net change",
        f"{money_text(result.net_change)}{suffix}",
    )

    if result.safe_to_export:
        st.success(
            "Validation passed. The consolidated reports are ready to download."
        )
    else:
        st.error(
            "Export is blocked because one or more safety checks need attention."
        )
        with st.expander("Why export is blocked", expanded=True):
            for reason in result.blocking_reasons:
                st.write(f"• {reason}")

    overview_tab, sources_tab, transactions_tab, monthly_tab, validation_tab = st.tabs(
        [
            "Overview",
            "Source statements",
            "Transactions",
            "Monthly summary",
            "Validation",
        ]
    )

    with overview_tab:
        left, right = st.columns([1, 1])

        with left:
            st.subheader("PDF intake")
            st.dataframe(
                result.inspections,
                use_container_width=True,
                hide_index=True,
            )

        with right:
            st.subheader("What the tool verified")
            st.markdown(
                """
                - PDF readability and duplicate uploads
                - Statement layout recognition
                - Transaction structure
                - Debit/credit consistency
                - Statement balance reconciliation
                - Cross-statement account/currency compatibility when detectable
                - Statement period overlap and balance continuity when detectable
                """
            )

    with sources_tab:
        st.caption(
            "Account identifiers are never displayed. Only whether a usable "
            "identifier was detected is shown."
        )
        st.dataframe(
            result.statements,
            use_container_width=True,
            hide_index=True,
        )

    with transactions_tab:
        st.dataframe(
            result.transactions,
            use_container_width=True,
            hide_index=True,
        )

    with monthly_tab:
        st.dataframe(
            result.monthly_summary,
            use_container_width=True,
            hide_index=True,
        )

    with validation_tab:
        st.dataframe(
            result.validation,
            use_container_width=True,
            hide_index=True,
        )

    if not result.safe_to_export:
        return

    st.subheader("Download consolidated reports")
    st.caption(
        "The generated files are consolidated reports derived from the uploaded "
        "statements. They are not official bank-issued statements."
    )

    excel_column, pdf_column = st.columns(2)

    with excel_column:
        st.download_button(
            "⬇️ Download Excel workbook",
            data=result.excel_report,
            file_name="consolidated_bank_statement_report.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

    with pdf_column:
        st.download_button(
            "⬇️ Download PDF report",
            data=result.pdf_report,
            file_name="consolidated_bank_statement_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


require_optional_passcode()

with st.sidebar:
    st.header("About this tool")
    st.write(
        "ConsolidatedState combines bank statement transactions using "
        "deterministic PDF parsing and financial validation."
    )

    st.subheader("Privacy")
    st.caption(
        "The application does not intentionally save uploaded statement files "
        "to the project filesystem or send them to an LLM API."
    )

    st.subheader("Current limits")
    st.caption(
        "Up to 12 PDFs per run, 20 MB per PDF. Image-only statements are "
        "detected but OCR support is still a future step."
    )

st.markdown(
    """
    <div class="cs-hero">
        <h1>📄 Bank Statement Consolidator</h1>
        <p>
            Combine monthly bank statements into one validated Excel workbook
            and one consolidated PDF report.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

step_1, step_2, step_3 = st.columns(3)

with step_1:
    st.markdown(
        """
        <div class="cs-step">
            <strong>1 · Upload</strong>
            Add 1–12 PDF statements for the account you want to consolidate.
        </div>
        """,
        unsafe_allow_html=True,
    )

with step_2:
    st.markdown(
        """
        <div class="cs-step">
            <strong>2 · Review</strong>
            The app parses the layout and checks balances, dates, duplicates,
            and statement compatibility.
        </div>
        """,
        unsafe_allow_html=True,
    )

with step_3:
    st.markdown(
        """
        <div class="cs-step">
            <strong>3 · Download</strong>
            If validation passes, download the consolidated Excel and PDF
            reports.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.info(
    "Statements can come from different banks and layouts. For one consolidated "
    "report they should normally represent the same account and currency."
)

uploaded_files = st.file_uploader(
    "Upload bank statement PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="Select up to 12 PDF statements. Each file can be up to 20 MB.",
    key="statement_uploads",
    on_change=clear_previous_result,
)

if uploaded_files:
    total_size_mb = sum(file.size for file in uploaded_files) / (1024 * 1024)
    st.caption(
        f"Selected {len(uploaded_files)} file(s) · "
        f"{total_size_mb:.2f} MB total"
    )

    if len(uploaded_files) > 12:
        st.error("Please upload no more than 12 statements at once.")
    else:
        if st.button(
            "Process statements",
            type="primary",
            use_container_width=True,
        ):
            inputs = [
                (uploaded.name, uploaded.getvalue())
                for uploaded in uploaded_files
            ]

            try:
                with st.spinner(
                    "Reading statements, validating transactions, and building the report..."
                ):
                    st.session_state["consolidation_result"] = (
                        process_statements(inputs)
                    )
            except Exception as exc:
                st.session_state.pop("consolidation_result", None)
                st.error(
                    "The statements could not be processed safely. "
                    f"Technical detail: {exc}"
                )

result = st.session_state.get("consolidation_result")
if isinstance(result, ConsolidationResult):
    render_result(result)
