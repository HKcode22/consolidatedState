from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl.styles import Font

DISCLAIMER = "Consolidated report derived from source statements. Not an official bank-issued statement."


def build_excel_report(
    transactions: pd.DataFrame,
    summary: pd.DataFrame,
    validation: pd.DataFrame,
) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        transactions.to_excel(writer, sheet_name="Transactions", index=False)
        summary.to_excel(writer, sheet_name="Monthly Summary", index=False)
        validation.to_excel(writer, sheet_name="Validation", index=False)

        workbook = writer.book
        info = workbook.create_sheet("About", 0)
        info["A1"] = "ConsolidatedState"
        info["A1"].font = Font(bold=True, size=14)
        info["A3"] = DISCLAIMER
        info.column_dimensions["A"].width = 95

        for sheet_name in ["Transactions", "Monthly Summary", "Validation"]:
            sheet = workbook[sheet_name]
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            for column_cells in sheet.columns:
                max_len = max((len(str(cell.value)) if cell.value is not None else 0) for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 45)

        tx_sheet = workbook["Transactions"]
        headers = {cell.value: cell.column for cell in tx_sheet[1]}
        for header in ("debit", "credit", "balance"):
            if header in headers:
                for col_cells in tx_sheet.iter_cols(min_col=headers[header], max_col=headers[header], min_row=2):
                    for cell in col_cells:
                        cell.number_format = '$#,##0.00;[Red]-$#,##0.00'

    return buffer.getvalue()
