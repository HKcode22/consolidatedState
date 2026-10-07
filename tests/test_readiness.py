import pandas as pd

from consolidated_state.readiness import export_is_safe


def frame(statuses):
    return pd.DataFrame(
        [
            {
                "source_file": f"s{i}.pdf",
                "check": "test",
                "status": status,
                "detail": "",
                "difference": None,
            }
            for i, status in enumerate(statuses, start=1)
        ]
    )


def test_export_allowed_only_when_every_uploaded_file_parsed_and_no_blockers():
    safe, reasons = export_is_safe(
        frame(["PASS", "PASS", "SKIPPED"]),
        uploaded_file_count=2,
        parsed_file_count=2,
    )
    assert safe is True
    assert reasons == []


def test_export_blocked_when_a_file_did_not_parse():
    safe, reasons = export_is_safe(
        frame(["PASS"]),
        uploaded_file_count=2,
        parsed_file_count=1,
    )
    assert safe is False
    assert any("Only 1 of 2" in reason for reason in reasons)


def test_export_blocked_on_validation_failure():
    safe, reasons = export_is_safe(
        frame(["PASS", "FAIL"]),
        uploaded_file_count=2,
        parsed_file_count=2,
    )
    assert safe is False
    assert any("FAIL" in reason for reason in reasons)


def test_export_blocked_on_ocr_or_duplicate_input():
    for status in ("OCR_REQUIRED", "DUPLICATE_FILE", "NEEDS_BANK_PARSER"):
        safe, reasons = export_is_safe(
            frame(["PASS", status]),
            uploaded_file_count=2,
            parsed_file_count=2,
        )
        assert safe is False
        assert any(status in reason for reason in reasons)
