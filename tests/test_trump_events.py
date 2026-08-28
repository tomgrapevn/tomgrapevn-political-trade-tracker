from tracker.data.trump_events import EVENT_CALENDAR, all_tickers, to_signals_frame


def test_event_calendar_entries_are_well_formed():
    assert len(EVENT_CALENDAR) > 0
    for event in EVENT_CALENDAR:
        assert event.direction in {"long", "short"}
        assert len(event.tickers) > 0
        assert event.source  # every claimed event must cite where it came from
        assert event.description


def test_to_signals_frame_expands_one_row_per_ticker():
    df = to_signals_frame()
    expected_rows = sum(len(e.tickers) for e in EVENT_CALENDAR)
    assert len(df) == expected_rows
    assert set(df.columns) >= {"signal_date", "ticker", "side", "category", "article_count"}


def test_to_signals_frame_is_sorted_by_date():
    df = to_signals_frame()
    assert df["signal_date"].is_monotonic_increasing


def test_all_tickers_matches_calendar():
    tickers = all_tickers()
    assert tickers == sorted(set(tickers))
    assert all(t == t.upper() for t in tickers)
