from __future__ import annotations

import pandas as pd

BLOCKING_STATUSES = {
    "ERROR",
    "TOO_LARGE",
    "PASSWORD_REQUIRED",
    "OCR_REQUIRED",
    "INVALID_PDF",
    "DUPLICATE_FILE",
    "NEEDS_BANK_PARSER",
    "FAIL",
    "NEEDS_REVIEW",
}


def export_is_safe(
    validation: pd.DataFrame,
    *,
    uploaded_file_count: int,
    parsed_file_count: int,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if uploaded_file_count == 0:
        reasons.append("No statements were uploaded.")

    if parsed_file_count != uploaded_file_count:
        reasons.append(
            f"Only {parsed_file_count} of {uploaded_file_count} uploaded statements were parsed successfully."
        )

    if not validation.empty and "status" in validation.columns:
        blocking = validation[validation["status"].isin(BLOCKING_STATUSES)]
        for _, row in blocking.iterrows():
            reasons.append(
                f"{row.get('source_file', 'unknown')}: "
                f"{row.get('check', 'validation')} -> {row.get('status', 'BLOCKED')}"
            )

    # Preserve order while removing duplicate messages.
    unique_reasons = list(dict.fromkeys(reasons))
    return (len(unique_reasons) == 0, unique_reasons)
