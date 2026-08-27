import pandas as pd

from tracker.pipeline import daily


def _make_congress_df(as_of: pd.Timestamp) -> pd.DataFrame:
    columns = [
        "chamber",
        "member",
        "ticker",
        "transaction_type",
        "transaction_date",
        "disclosure_date",
        "amount_range",
        "owner",
        "asset_description",
        "disclosure_lag_days",
    ]
    in_window = {
        "chamber": "senate",
        "member": "Sen. Alpha Example",
        "ticker": "AAPL",
        "transaction_type": "purchase",
        "transaction_date": as_of - pd.Timedelta(days=30),
        "disclosure_date": as_of - pd.Timedelta(hours=2),
        "amount_range": "$1,001 - $15,000",
        "owner": "self",
        "asset_description": "AAPL common stock",
        "disclosure_lag_days": 30,
    }
    out_of_window = {**in_window, "ticker": "XOM", "disclosure_date": as_of - pd.Timedelta(days=10)}
    return pd.DataFrame([in_window, out_of_window])[columns]


def test_run_daily_only_signals_on_trades_disclosed_within_the_window(monkeypatch):
    as_of = pd.Timestamp("2024-06-15 07:00:00")
    congress_df = _make_congress_df(as_of)

    monkeypatch.setattr(daily.disclosures_data, "fetch_disclosures", lambda: congress_df)
    monkeypatch.setattr(daily.disclosures_data, "filter_watchlist", lambda df, wl: df)
    monkeypatch.setattr(daily.insider_data, "fetch_insider_trades", lambda: congress_df.iloc[0:0])
    monkeypatch.setattr(
        daily.news_data,
        "fetch_policy_news",
        lambda start, end: pd.DataFrame(
            {"keyword": ["Iran"] * 5, "published_at": [as_of - pd.Timedelta(hours=1)] * 5}
        ),
    )
    monkeypatch.setattr(daily.fx, "resolve_capital_usd", lambda: (650.0, 1.30))
    monkeypatch.setattr(
        daily,
        "signals_to_orders",
        lambda signals, equity, pct: pd.DataFrame(
            {"ticker": signals["ticker"].unique(), "side": "buy", "notional_usd": pct * equity}
        ),
    )

    result = daily.run_daily(as_of=as_of, dry_run=True)

    assert result.capital_usd == 650.0
    assert result.news_articles == 5
    # only the disclosure inside the last-24h window becomes a signal
    assert len(result.trade_signals) == 1
    assert result.trade_signals.iloc[0]["ticker"] == "AAPL"
    # Iran is in event_map.py -> real signals generated from the news window
    assert not result.event_signals.empty
    # no Alpaca keys configured by default -> logged only, nothing submitted
    assert result.order_results
    assert all(r["status"] == "logged_only_no_broker_configured" for r in result.order_results)


def test_run_daily_passes_the_requested_window_to_news_fetch(monkeypatch):
    as_of = pd.Timestamp("2024-06-15 07:00:00")
    captured = {}

    monkeypatch.setattr(daily.disclosures_data, "fetch_disclosures", lambda: pd.DataFrame())
    monkeypatch.setattr(daily.disclosures_data, "filter_watchlist", lambda df, wl: df)
    monkeypatch.setattr(daily.insider_data, "fetch_insider_trades", lambda: pd.DataFrame())

    def fake_fetch_news(start, end):
        captured["start"] = start
        captured["end"] = end
        return pd.DataFrame(columns=["keyword", "published_at"])

    monkeypatch.setattr(daily.news_data, "fetch_policy_news", fake_fetch_news)
    monkeypatch.setattr(daily.fx, "resolve_capital_usd", lambda: (500.0, 1.25))

    daily.run_daily(as_of=as_of, window_hours=6, dry_run=True)

    assert (as_of - pd.Timestamp(captured["start"])) == pd.Timedelta(hours=6)
    assert pd.Timestamp(captured["end"]) == as_of


def test_run_daily_with_no_signals_produces_no_orders(monkeypatch):
    as_of = pd.Timestamp("2024-06-15 07:00:00")
    monkeypatch.setattr(daily.disclosures_data, "fetch_disclosures", lambda: pd.DataFrame())
    monkeypatch.setattr(daily.disclosures_data, "filter_watchlist", lambda df, wl: df)
    monkeypatch.setattr(daily.insider_data, "fetch_insider_trades", lambda: pd.DataFrame())
    monkeypatch.setattr(daily.news_data, "fetch_policy_news", lambda start, end: pd.DataFrame(columns=["keyword", "published_at"]))
    monkeypatch.setattr(daily.fx, "resolve_capital_usd", lambda: (500.0, 1.25))

    result = daily.run_daily(as_of=as_of, dry_run=True)

    assert result.trade_signals.empty
    assert result.event_signals.empty
    assert result.orders.empty
    assert result.order_results == []
