from io import BytesIO

import fitz
import pytest

from consolidated_state.parser import UnsupportedStatementFormat, parse_statement


def _pdf_bytes(lines):
    document = fitz.open()
    page = document.new_page()
    for x, y, text in lines:
        page.insert_text((x, y), text, fontsize=9)
    data = document.tobytes()
    document.close()
    return data


def _text(data):
    with fitz.open(stream=data, filetype="pdf") as document:
        return "\n".join(page.get_text("text") for page in document)


def test_unknown_statement_is_refused_instead_of_guessed():
    with pytest.raises(UnsupportedStatementFormat):
        parse_statement("01/01 SOME TRANSACTION 12.34", "unknown.pdf")


def test_generic_ledger_layout_without_bank_name():
    data = _pdf_bytes(
        [
            (40, 70, "Date"),
            (150, 70, "Transaction Details"),
            (400, 70, "Debit"),
            (470, 70, "Credit"),
            (540, 70, "Balance"),
            (40, 90, "01/01/26"),
            (150, 90, "Payroll deposit"),
            (470, 90, "100.00"),
            (540, 90, "1,100.00"),
            (40, 110, "01/02/26"),
            (150, 110, "Coffee"),
            (400, 110, "5.00"),
            (540, 110, "1,095.00"),
        ]
    )

    result = parse_statement(_text(data), "ledger.pdf", pdf_bytes=data)

    assert result.parser_name == "ledger-date-debit-credit-balance-v1"
    assert len(result.transactions) == 2
    assert result.statement.opening_balance is not None
    assert result.statement.closing_balance is not None
    assert str(result.statement.opening_balance) == "1000.00"
    assert str(result.statement.closing_balance) == "1095.00"


def test_generic_sectioned_layout_without_bank_name():
    data = _pdf_bytes(
        [
            (40, 50, "Beginning balance"),
            (500, 50, "$1,000.00"),
            (40, 90, "Deposits and other additions"),
            (40, 110, "Date"),
            (150, 110, "Description"),
            (520, 110, "Amount"),
            (40, 130, "01/01/26"),
            (150, 130, "Payroll"),
            (520, 130, "100.00"),
            (40, 170, "Withdrawals and other subtractions"),
            (40, 190, "Date"),
            (150, 190, "Description"),
            (520, 190, "Amount"),
            (40, 210, "01/02/26"),
            (150, 210, "Coffee"),
            (520, 210, "5.00"),
            (40, 250, "Ending balance"),
            (500, 250, "$1,095.00"),
        ]
    )

    result = parse_statement(_text(data), "sectioned.pdf", pdf_bytes=data)

    assert result.parser_name == "sectioned-date-description-amount-v1"
    assert len(result.transactions) == 2
    assert str(result.transactions[0].credit) == "100.00"
    assert str(result.transactions[1].debit) == "5.00"
    assert str(result.statement.opening_balance) == "1000.00"
    assert str(result.statement.closing_balance) == "1095.00"
