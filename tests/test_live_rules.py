from tracker.data.live_rules import LIVE_RULES, match_rules


def test_match_rules_finds_known_escalation_keyword():
    matches = match_rules("Iran strikes Israel with ballistic missiles overnight")
    categories = {r.category for r in matches}
    assert "middle_east_escalation" in categories


def test_match_rules_is_case_insensitive():
    matches = match_rules("IRAN STRIKES ISRAEL")
    assert any(r.category == "middle_east_escalation" for r in matches)


def test_match_rules_returns_empty_for_unrelated_text():
    assert match_rules("Local council approves new bike lane") == []


def test_match_rules_flags_deescalation_as_not_validated():
    matches = match_rules("Ceasefire agreed between warring parties")
    assert matches
    assert all(not r.validated for r in matches)


def test_every_validated_rule_has_at_least_one_ticker():
    for rule in LIVE_RULES:
        if rule.validated:
            assert rule.tickers_long or rule.tickers_short


def test_every_rule_has_a_note_explaining_the_backtest_basis():
    for rule in LIVE_RULES:
        assert rule.note
