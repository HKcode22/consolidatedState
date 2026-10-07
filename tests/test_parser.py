import pytest

from consolidated_state.parser import UnsupportedStatementFormat, parse_statement


def test_unknown_statement_is_refused_instead_of_guessed():
    with pytest.raises(UnsupportedStatementFormat):
        parse_statement("01/01 SOME TRANSACTION 12.34", "unknown.pdf")
