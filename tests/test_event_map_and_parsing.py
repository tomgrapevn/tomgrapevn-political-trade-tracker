import math

from tracker.data.event_map import EVENT_RULES, all_keywords, all_tickers
from tracker.models.features import _parse_amount_range


def test_event_rules_are_well_formed():
    assert len(EVENT_RULES) > 0
    for rule in EVENT_RULES:
        assert rule.direction in {"long", "short"}
        assert len(rule.tickers) > 0
        assert all(t == t.upper() for t in rule.tickers)
        assert rule.rationale  # never empty — every hypothesis must state its reasoning


def test_all_keywords_and_tickers_nonempty():
    assert len(all_keywords()) > 0
    assert len(all_tickers()) > 0


def test_parse_amount_range_midpoint():
    assert _parse_amount_range("$1,001 - $15,000") == (1001 + 15000) / 2


def test_parse_amount_range_handles_garbage():
    assert math.isnan(_parse_amount_range("not a range"))
    assert math.isnan(_parse_amount_range(None))
