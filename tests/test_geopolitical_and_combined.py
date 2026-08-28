from tracker.data.combined_conflict import all_conflict_tickers, combined_conflict_signals
from tracker.data.geopolitical_events import EVENT_CALENDAR, all_tickers, to_signals_frame


def test_geopolitical_calendar_entries_are_well_formed():
    assert len(EVENT_CALENDAR) > 0
    for event in EVENT_CALENDAR:
        assert event.direction in {"long", "short"}
        assert len(event.tickers) > 0
        assert event.source
        assert event.category in {"conflict_escalation", "conflict_deescalation"}


def test_geopolitical_to_signals_frame_shape():
    df = to_signals_frame()
    expected = sum(len(e.tickers) for e in EVENT_CALENDAR)
    assert len(df) == expected


def test_all_tickers_nonempty():
    assert len(all_tickers()) > 0


def test_combined_conflict_escalation_only_excludes_deescalation():
    df = combined_conflict_signals(include_deescalation=False)
    assert not df.empty
    assert (~df["category"].str.endswith("deescalation")).all()
    assert df["category"].str.contains("conflict").all()


def test_combined_conflict_with_deescalation_includes_both():
    escalation_only = combined_conflict_signals(include_deescalation=False)
    with_deescalation = combined_conflict_signals(include_deescalation=True)
    assert len(with_deescalation) > len(escalation_only)
    assert with_deescalation["category"].str.endswith("deescalation").any()


def test_combined_conflict_merges_both_source_calendars():
    df = combined_conflict_signals(include_deescalation=True)
    # Trump/Iran categories and generic conflict_escalation categories should
    # both be present — this is the whole point of the merge.
    assert "middle_east_conflict" in set(df["category"])
    assert "conflict_escalation" in set(df["category"])


def test_all_conflict_tickers_is_union_of_both_calendars():
    from tracker.data.trump_events import all_tickers as trump_tickers

    combined = set(all_conflict_tickers())
    assert set(trump_tickers()) <= combined
    assert set(all_tickers()) <= combined
