from __future__ import annotations

from html import escape
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .report_data import build_overview_frame, build_statement_frame
from .models import StatementSummary

DISCLAIMER = (
    "Consolidated report derived from source statements. "
    "Not an official bank-issued statement."
)


def _display(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            pass

    if isinstance(value, float):
        return f"{value:,.2f}"

    return str(value)


def _money(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return f"{value:,.2f}"
    except Exception:
        return str(value)


def _cell(value: object, style) -> Paragraph:
    return Paragraph(escape(_display(value)), style)


def _section_title(story: list, text: str, styles) -> None:
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(escape(text), styles["Heading2"]))
    story.append(Spacer(1, 0.06 * inch))


def _table(
    headers: list[str],
    rows: list[list[object]],
    widths: list[float],
    body_style,
    *,
    money_columns: set[int] | None = None,
) -> LongTable:
    money_columns = money_columns or set()

    data: list[list[object]] = [
        [Paragraph(f"<b>{escape(header)}</b>", body_style) for header in headers]
    ]

    for row in rows:
        rendered: list[object] = []
        for index, value in enumerate(row):
            text = _money(value) if index in money_columns else _display(value)
            rendered.append(Paragraph(escape(text), body_style))
        data.append(rendered)

    table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        0.45 * inch,
        0.25 * inch,
        "Consolidated report - not an official bank statement",
    )
    canvas.drawRightString(
        landscape(letter)[0] - 0.45 * inch,
        0.25 * inch,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def build_pdf_report(
    transactions: pd.DataFrame,
    summary: pd.DataFrame,
    validation: pd.DataFrame,
    statements: list[StatementSummary] | None = None,
) -> bytes:
    statements = statements or []

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title="Consolidated Bank Statement Report",
        author="ConsolidatedState",
    )

    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 7
    styles["BodyText"].leading = 9

    story: list[object] = []
    story.append(Paragraph("Consolidated Bank Statement Report", styles["Title"]))
    story.append(Paragraph(DISCLAIMER, styles["BodyText"]))
    story.append(Spacer(1, 0.14 * inch))

    overview = build_overview_frame(transactions, statements)
    overview_rows = [
        [row["Metric"], row["Value"]]
        for _, row in overview.iterrows()
    ]
    story.append(
        _table(
            ["Metric", "Value"],
            overview_rows,
            [2.6 * inch, 3.3 * inch],
            styles["BodyText"],
            money_columns=set(),
        )
    )

    _section_title(story, "Source Statements", styles)
    source = build_statement_frame(statements)
    source_rows = [
        [
            row["source_file"],
            row["statement_period"],
            row["currency"],
            "Yes" if row["account_identifier_detected"] else "No",
            row["opening_balance"],
            row["closing_balance"],
            row["layout_strategy"],
        ]
        for _, row in source.iterrows()
    ]
    story.append(
        _table(
            [
                "Source file",
                "Statement period",
                "Currency",
                "Account ID detected",
                "Opening balance",
                "Closing balance",
                "Layout strategy",
            ],
            source_rows,
            [
                1.55 * inch,
                1.55 * inch,
                0.85 * inch,
                0.85 * inch,
                1.0 * inch,
                1.0 * inch,
                2.45 * inch,
            ],
            styles["BodyText"],
            money_columns={4, 5},
        )
    )

    credits = transactions[transactions["credit"].notna()].copy()
    _section_title(story, "Credits / Deposits / Additions", styles)
    credit_rows = [
        [
            row["date"],
            row["description"],
            row["credit"],
            row["source_file"],
        ]
        for _, row in credits.iterrows()
    ]
    story.append(
        _table(
            ["Date", "Description", "Amount", "Source"],
            credit_rows,
            [0.9 * inch, 5.25 * inch, 1.15 * inch, 2.15 * inch],
            styles["BodyText"],
            money_columns={2},
        )
    )

    debits = transactions[transactions["debit"].notna()].copy()
    _section_title(story, "Debits / Withdrawals / Subtractions", styles)
    debit_rows = [
        [
            row["date"],
            row["description"],
            row["debit"],
            row["source_file"],
        ]
        for _, row in debits.iterrows()
    ]
    story.append(
        _table(
            ["Date", "Description", "Amount", "Source"],
            debit_rows,
            [0.9 * inch, 5.25 * inch, 1.15 * inch, 2.15 * inch],
            styles["BodyText"],
            money_columns={2},
        )
    )

    _section_title(story, "Monthly Summary", styles)
    monthly_rows = [
        [
            row["month"],
            row["total_debits"],
            row["total_credits"],
            row["net"],
        ]
        for _, row in summary.iterrows()
    ]
    story.append(
        _table(
            ["Month", "Debits", "Credits", "Net"],
            monthly_rows,
            [1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch],
            styles["BodyText"],
            money_columns={1, 2, 3},
        )
    )

    _section_title(story, "Validation", styles)
    validation_rows = [
        [
            row.get("source_file", ""),
            row.get("check", ""),
            row.get("status", ""),
            row.get("detail", ""),
        ]
        for _, row in validation.iterrows()
    ]
    story.append(
        _table(
            ["Source", "Check", "Status", "Detail"],
            validation_rows,
            [1.55 * inch, 1.55 * inch, 1.0 * inch, 5.9 * inch],
            styles["BodyText"],
        )
    )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
