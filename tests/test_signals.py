import pandas as pd

from tracker.data.disclosures import filter_watchlist
from tracker.signals import event_driven, mirror_trade


def test_mirror_signals_default_to_long_only(sample_disclosures):
    signals = mirror_trade.generate_signals(sample_disclosures)
    assert set(signals["side"]) == {"long"}
    assert signals["signal_date"].notna().all()

    # signal date must be exactly the *disclosure* date of the source row,
    # never the (earlier) transaction date — that's the realistic constraint
    # this strategy is built around.
    purchases = sample_disclosures[sample_disclosures["transaction_type"] == "purchase"]
    assert set(signals["signal_date"]) == set(purchases["disclosure_date"])
    assert len(signals) == len(purchases)


def test_mirror_signals_collapse_same_day_line_items_into_one_signal():
    # A single real buying decision can be filed as many line items (e.g. a
    # block purchase split across several trade confirmations at different
    # prices, all in one Form 4/PTR) — verified live against a real Musk
    # Form 4 while building this. Each line item must not count as its own
    # trade in the backtest.
    same_day = pd.DataFrame(
        [
            {
                "chamber": "insider",
                "member": "Elon Musk",
                "ticker": "TSLA",
                "transaction_type": "purchase",
                "transaction_date": pd.Timestamp("2025-09-12"),
                "disclosure_date": pd.Timestamp("2025-09-15"),
                "amount_range": f"${1000 * i} - ${1000 * i}",
                "owner": "self",
                "asset_description": "TSLA common stock",
                "disclosure_lag_days": 3,
            }
            for i in range(1, 26)
        ]
    )
    signals = mirror_trade.generate_signals(same_day)
    assert len(signals) == 1
    assert signals.iloc[0]["ticker"] == "TSLA"


def test_mirror_signals_include_shorts_when_requested(sample_disclosures):
    signals = mirror_trade.generate_signals(sample_disclosures, include_shorts=True)
    assert "short" in set(signals["side"])


def test_filter_watchlist_case_insensitive_substring(sample_disclosures):
    filtered = filter_watchlist(sample_disclosures, ["alpha example"])
    assert len(filtered) > 0
    assert (filtered["member"] == "Sen. Alpha Example").all()


def test_filter_watchlist_empty_is_noop(sample_disclosures):
    assert len(filter_watchlist(sample_disclosures, [])) == len(sample_disclosures)


def test_event_signals_expand_keyword_to_mapped_tickers(sample_daily_events):
    signals = event_driven.generate_signals(sample_daily_events, min_article_count=3)
    assert not signals.empty
    assert "XLE" in set(signals.loc[signals["keyword"] == "Iran", "ticker"])


def test_event_signals_respect_article_count_threshold(sample_daily_events):
    loose = event_driven.generate_signals(sample_daily_events, min_article_count=1)
    strict = event_driven.generate_signals(sample_daily_events, min_article_count=100)
    assert len(strict) == 0
    assert len(loose) > 0
