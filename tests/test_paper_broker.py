import pandas as pd
import pytest

from tracker.execution.paper_broker import (
    LiveTradingBlockedError,
    PaperBrokerClient,
    execute_orders,
    signals_to_orders,
)


def test_paper_broker_refuses_non_paper_endpoint():
    with pytest.raises(LiveTradingBlockedError):
        PaperBrokerClient(api_key="x", secret_key="y", base_url="https://api.alpaca.markets")


def test_paper_broker_accepts_paper_endpoint():
    client = PaperBrokerClient(api_key="x", secret_key="y", base_url="https://paper-api.alpaca.markets")
    assert client.base_url == "https://paper-api.alpaca.markets"


def test_signals_to_orders_sizes_by_max_position_pct():
    signals = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "ticker": ["AAPL", "XOM"],
            "side": ["long", "long"],
        }
    )
    orders = signals_to_orders(signals, account_equity=1000.0, max_position_pct=0.10)
    assert set(orders["ticker"]) == {"AAPL", "XOM"}
    assert (orders["notional_usd"] == 100.0).all()
    assert set(orders["side"]) == {"buy"}


def test_signals_to_orders_keeps_only_latest_signal_per_ticker():
    signals = pd.DataFrame(
        {
            "signal_date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "ticker": ["AAPL", "AAPL"],
            "side": ["long", "short"],
        }
    )
    orders = signals_to_orders(signals, account_equity=1000.0, max_position_pct=0.10)
    assert len(orders) == 1
    assert orders.iloc[0]["side"] == "sell"


def test_execute_orders_dry_run_makes_no_network_call():
    orders = pd.DataFrame({"ticker": ["AAPL"], "side": ["buy"], "notional_usd": [50.0]})
    results = execute_orders(client=None, orders=orders, dry_run=True)
    assert results[0]["status"] == "dry_run"
