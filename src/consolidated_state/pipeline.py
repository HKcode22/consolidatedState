from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from .consolidate import (
    currency_summary,
    find_duplicate_transactions,
    monthly_summary,
    transactions_to_frame,
)
from .export_excel import build_excel_report
from .export_pdf import build_pdf_report
from .models import StatementSummary
from .parser import UnsupportedStatementFormat, parse_statement
from .pdf_inspect import inspect_and_extract_pdf
from .readiness import export_is_safe
from .report_data import build_statement_frame
from .validate import (
    reconcile_statement,
    validate_statement_set,
    validate_transaction_rows,
)


@dataclass
class ConsolidationResult:
    inspections: pd.DataFrame
    statements: pd.DataFrame
    transactions: pd.DataFrame
    monthly_summary: pd.DataFrame
    currency_summary: pd.DataFrame
    validation: pd.DataFrame
    safe_to_export: bool
    blocking_reasons: list[str]
    excel_report: bytes | None
    pdf_report: bytes | None
    total_credits: Decimal | None
    total_debits: Decimal | None
    combined_currency: str | None

    @property
    def net_change(self) -> Decimal | None:
        if self.total_credits is None or self.total_debits is None:
            return None
        return self.total_credits - self.total_debits


def _combined_totals(
    summary: pd.DataFrame,
) -> tuple[Decimal | None, Decimal | None, str | None]:
    if len(summary) != 1:
        return None, None, None

    row = summary.iloc[0]
    credits = row["total_credits"]
    debits = row["total_debits"]
    currency_label = str(row["currency"])

    return (
        credits if isinstance(credits, Decimal) else Decimal(str(credits)),
        debits if isinstance(debits, Decimal) else Decimal(str(debits)),
        None if currency_label.startswith("Unknown (") else currency_label,
    )


def process_statements(
    files: list[tuple[str, bytes]],
) -> ConsolidationResult:
    """Run the complete deterministic consolidation pipeline.

    Each input is a (filename, PDF-bytes) pair. No statement bytes are written
    to disk by this function.
    """
    if not files:
        raise ValueError("At least one PDF statement is required.")

    if len(files) > 12:
        raise ValueError("No more than 12 statements can be processed at once.")

    inspections: list[dict[str, object]] = []
    all_transactions = []
    statement_summaries: list[StatementSummary] = []
    validation_rows: list[dict[str, object]] = []
    seen_hashes: dict[str, str] = {}
    parsed_files: set[str] = set()

    for source_file, pdf_bytes in files:
        inspection, text = inspect_and_extract_pdf(pdf_bytes, source_file)

        duplicate_of = seen_hashes.get(inspection.sha256)
        if duplicate_of is None:
            seen_hashes[inspection.sha256] = source_file

        intake_status = (
            "DUPLICATE_FILE"
            if duplicate_of
            else inspection.status
        )
        intake_detail = (
            f"Exact duplicate of {duplicate_of}."
            if duplicate_of
            else inspection.detail
        )

        inspections.append(
            {
                "source_file": inspection.source_file,
                "pages": inspection.page_count,
                "size_mb": round(
                    inspection.size_bytes / (1024 * 1024),
                    2,
                ),
                "embedded_text": inspection.has_text,
                "status": intake_status,
                "detail": intake_detail,
            }
        )

        validation_rows.append(
            {
                "source_file": source_file,
                "check": "pdf_intake",
                "status": (
                    "PASS"
                    if intake_status == "TEXT_READY"
                    else intake_status
                ),
                "detail": intake_detail,
                "difference": None,
            }
        )

        if duplicate_of or inspection.status != "TEXT_READY":
            continue

        try:
            parsed = parse_statement(
                text,
                source_file,
                pdf_bytes=pdf_bytes,
            )
        except UnsupportedStatementFormat as exc:
            validation_rows.append(
                {
                    "source_file": source_file,
                    "check": "parser",
                    "status": "NEEDS_LAYOUT_STRATEGY",
                    "detail": str(exc),
                    "difference": None,
                }
            )
            continue

        all_transactions.extend(parsed.transactions)
        statement_summaries.append(parsed.statement)
        parsed_files.add(source_file)
        validation_rows.append(
            {
                "source_file": source_file,
                "check": "parser",
                "status": "PASS",
                "detail": f"Parsed with {parsed.parser_name}.",
                "difference": None,
            }
        )

    inspection_frame = pd.DataFrame(inspections)
    transaction_frame = transactions_to_frame(all_transactions)
    statement_frame = build_statement_frame(statement_summaries)
    currency_frame = currency_summary(transaction_frame)

    if transaction_frame.empty:
        validation_frame = pd.DataFrame(validation_rows)
        safe, reasons = export_is_safe(
            validation_frame,
            uploaded_file_count=len(files),
            parsed_file_count=len(parsed_files),
        )
        return ConsolidationResult(
            inspections=inspection_frame,
            statements=statement_frame,
            transactions=transaction_frame,
            monthly_summary=monthly_summary(transaction_frame),
            currency_summary=currency_frame,
            validation=validation_frame,
            safe_to_export=safe,
            blocking_reasons=reasons,
            excel_report=None,
            pdf_report=None,
            total_credits=Decimal("0.00"),
            total_debits=Decimal("0.00"),
            combined_currency=None,
        )

    validation_rows.append(
        validate_transaction_rows(transaction_frame)
    )
    validation_rows.extend(
        validate_statement_set(statement_summaries)
    )

    duplicate_transactions = find_duplicate_transactions(
        transaction_frame,
        statement_summaries,
    )
    if not duplicate_transactions.empty:
        validation_rows.append(
            {
                "source_file": "ALL",
                "check": "duplicate_transactions",
                "status": "NEEDS_REVIEW",
                "detail": (
                    f"Found {len(duplicate_transactions)} rows "
                    "participating in possible duplicates across statements "
                    "from the same detected account."
                ),
                "difference": None,
            }
        )

    for statement in statement_summaries:
        validation_rows.append(
            reconcile_statement(
                statement,
                transaction_frame,
            )
        )

    validation_frame = pd.DataFrame(validation_rows)
    summary_frame = monthly_summary(transaction_frame)

    safe, reasons = export_is_safe(
        validation_frame,
        uploaded_file_count=len(files),
        parsed_file_count=len(parsed_files),
    )

    total_credits, total_debits, combined_currency = _combined_totals(
        currency_frame
    )

    excel_report = None
    pdf_report = None

    if safe:
        excel_report = build_excel_report(
            transaction_frame,
            summary_frame,
            validation_frame,
            statement_summaries,
        )
        pdf_report = build_pdf_report(
            transaction_frame,
            summary_frame,
            validation_frame,
            statement_summaries,
        )

    return ConsolidationResult(
        inspections=inspection_frame,
        statements=statement_frame,
        transactions=transaction_frame,
        monthly_summary=summary_frame,
        currency_summary=currency_frame,
        validation=validation_frame,
        safe_to_export=safe,
        blocking_reasons=reasons,
        excel_report=excel_report,
        pdf_report=pdf_report,
        total_credits=total_credits,
        total_debits=total_debits,
        combined_currency=combined_currency,
    )
