from __future__ import annotations

from html import escape
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from .consolidate import currency_summary
from .models import StatementSummary
from .report_data import build_overview_frame, build_statement_frame

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
    story.append(
        Paragraph(
            "Different or unidentified currencies are kept separate. "
            "No currency conversion is performed.",
            styles["BodyText"],
        )
    )
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
        )
    )

    _section_title(story, "Currency Summary", styles)
    currencies = currency_summary(transactions)
    currency_rows = [
        [
            row["currency"],
            row["source_statements"],
            row["transactions"],
            row["total_debits"],
            row["total_credits"],
            row["net"],
        ]
        for _, row in currencies.iterrows()
    ]
    story.append(
        _table(
            ["Currency", "Sources", "Transactions", "Debits", "Credits", "Net"],
            currency_rows,
            [1.8 * inch, 0.8 * inch, 0.9 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch],
            styles["BodyText"],
            money_columns={3, 4, 5},
        )
    )

    _section_title(story, "Source Statements", styles)
    source = build_statement_frame(statements)
    source_rows = [
        [
            row["source_file"],
            row["account_group"],
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
                "Account group",
                "Statement period",
                "Currency",
                "Account ID detected",
                "Opening balance",
                "Closing balance",
                "Layout strategy",
            ],
            source_rows,
            [
                1.35 * inch,
                0.8 * inch,
                1.35 * inch,
                0.9 * inch,
                0.75 * inch,
                0.95 * inch,
                0.95 * inch,
                2.1 * inch,
            ],
            styles["BodyText"],
            money_columns={5, 6},
        )
    )

    credits = transactions[transactions["credit"].notna()].copy()
    _section_title(story, "Credits / Deposits / Additions", styles)
    credit_rows = [
        [
            row["date"],
            row["description"],
            row["credit"],
            row["currency"] or f"Unknown ({row['source_file']})",
            row["source_file"],
        ]
        for _, row in credits.iterrows()
    ]
    story.append(
        _table(
            ["Date", "Description", "Amount", "Currency", "Source"],
            credit_rows,
            [0.8 * inch, 4.8 * inch, 1.1 * inch, 1.25 * inch, 1.8 * inch],
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
            row["currency"] or f"Unknown ({row['source_file']})",
            row["source_file"],
        ]
        for _, row in debits.iterrows()
    ]
    story.append(
        _table(
            ["Date", "Description", "Amount", "Currency", "Source"],
            debit_rows,
            [0.8 * inch, 4.8 * inch, 1.1 * inch, 1.25 * inch, 1.8 * inch],
            styles["BodyText"],
            money_columns={2},
        )
    )

    _section_title(story, "Monthly Summary", styles)
    monthly_rows = [
        [
            row["currency"],
            row["month"],
            row["total_debits"],
            row["total_credits"],
            row["net"],
        ]
        for _, row in summary.iterrows()
    ]
    story.append(
        _table(
            ["Currency", "Month", "Debits", "Credits", "Net"],
            monthly_rows,
            [2.3 * inch, 1.2 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch],
            styles["BodyText"],
            money_columns={2, 3, 4},
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
