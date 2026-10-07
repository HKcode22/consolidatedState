from consolidated_state.access import passcode_matches


def test_passcode_gate_is_open_when_no_passcode_is_configured():
    assert passcode_matches("anything", "") is True


def test_passcode_gate_requires_exact_match_when_configured():
    assert passcode_matches("family-secret", "family-secret") is True
    assert passcode_matches("wrong", "family-secret") is False
