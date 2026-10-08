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


def render_result(result: ConsolidationResult) -> None:
    st.divider()

    top_metrics = st.columns(2)
    top_metrics[0].metric(
        "Statements parsed",
        len(result.statements),
    )
    top_metrics[1].metric(
        "Transactions",
        len(result.transactions),
    )

    if result.total_credits is not None and result.total_debits is not None:
        suffix = (
            f" {result.combined_currency}"
            if result.combined_currency
            else " (currency not identified)"
        )
        money_metrics = st.columns(3)
        money_metrics[0].metric(
            "Deposits / credits",
            f"{money_text(result.total_credits)}{suffix}",
        )
        money_metrics[1].metric(
            "Withdrawals / debits",
            f"{money_text(result.total_debits)}{suffix}",
        )
        money_metrics[2].metric(
            "Net change",
            f"{money_text(result.net_change)}{suffix}",
        )
    else:
        st.warning(
            "Grand monetary totals are intentionally not combined because the "
            "uploaded statements contain multiple or unresolved currencies. "
            "Use the Currency summary below; no currency conversion is performed."
        )
        st.dataframe(
            result.currency_summary,
            use_container_width=True,
            hide_index=True,
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

    (
        overview_tab,
        sources_tab,
        currency_tab,
        transactions_tab,
        monthly_tab,
        validation_tab,
    ) = st.tabs(
        [
            "Overview",
            "Source statements",
            "Currency summary",
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
                - Per-statement balance reconciliation
                - Account grouping when identifiers are detectable
                - Period overlap/gaps only within the same detected account
                - Currency separation with no automatic conversion
                """
            )

    with sources_tab:
        st.caption(
            "Actual account identifiers are never displayed. Statements are given "
            "non-sensitive account-group labels when a usable identifier is detected."
        )
        st.dataframe(
            result.statements,
            use_container_width=True,
            hide_index=True,
        )

    with currency_tab:
        st.caption(
            "Different currencies are never added together. Unknown-currency "
            "statements are kept separate by source file."
        )
        st.dataframe(
            result.currency_summary,
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
        st.caption(
            "Monthly totals are grouped by currency. Unknown currencies remain "
            "separate by source rather than being mixed into another currency."
        )
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
            Add 1–12 PDF statements you want included in the consolidated report.
        </div>
        """,
        unsafe_allow_html=True,
    )

with step_2:
    st.markdown(
        """
        <div class="cs-step">
            <strong>2 · Review</strong>
            The app parses each layout and validates balances, dates, accounts,
            duplicates, and currency handling.
        </div>
        """,
        unsafe_allow_html=True,
    )

with step_3:
    st.markdown(
        """
        <div class="cs-step">
            <strong>3 · Download</strong>
            If validation passes, download the consolidated Excel and PDF reports.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.info(
    "Statements may come from different banks and accounts. If currencies differ "
    "or cannot be identified, their monetary totals are kept separate and are "
    "never silently converted or added together."
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
