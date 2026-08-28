import pandas as pd

from tracker.data.macro_calendar import FOMC_MEETINGS, to_signals_frame


def test_fomc_meetings_are_two_day_pairs_in_order():
    for start, decision in FOMC_MEETINGS:
        start_ts, decision_ts = pd.Timestamp(start), pd.Timestamp(decision)
        assert start_ts < decision_ts
        assert (decision_ts - start_ts).days <= 2  # consecutive business days


def test_meetings_roughly_eight_per_year():
    years = pd.Series([pd.Timestamp(s).year for s, _ in FOMC_MEETINGS])
    counts = years.value_counts()
    assert (counts == 8).all()


def test_to_signals_frame_one_row_per_meeting():
    df = to_signals_frame()
    assert len(df) == len(FOMC_MEETINGS)
    assert set(df["side"]) == {"long"}
    assert set(df["category"]) == {"fomc_pre_drift"}
    assert df["signal_date"].is_monotonic_increasing
