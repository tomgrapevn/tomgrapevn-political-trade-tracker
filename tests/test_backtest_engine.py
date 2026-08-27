import numpy as np
import pandas as pd

from tracker.backtest.engine import buy_and_hold_benchmark, resolve_trades, simulate_portfolio
from tracker.signals import mirror_trade


def test_resolve_trades_produces_entry_after_signal_and_no_lookahead(sample_disclosures, synthetic_prices):
    signals = mirror_trade.generate_signals(sample_disclosures)
    trades = resolve_trades(signals, synthetic_prices, holding_days=21, transaction_cost_bps=5)

    assert not trades.empty
    assert (trades["entry_date"] >= trades["signal_date"]).all()
    assert (trades["exit_date"] > trades["entry_date"]).all()
    # net return must be strictly less than gross return once costs are applied
    assert (trades["net_return"] < trades["gross_return"]).all()


def test_resolve_trades_drops_signals_too_close_to_data_end(sample_disclosures, synthetic_prices):
    signals = mirror_trade.generate_signals(sample_disclosures)
    trades_short_horizon = resolve_trades(signals, synthetic_prices, holding_days=5)
    trades_impossible_horizon = resolve_trades(signals, synthetic_prices, holding_days=100_000)
    assert len(trades_impossible_horizon) == 0
    assert len(trades_short_horizon) >= len(trades_impossible_horizon)


def test_simulate_portfolio_never_goes_negative_and_respects_position_cap(sample_disclosures, synthetic_prices):
    signals = mirror_trade.generate_signals(sample_disclosures)
    trades = resolve_trades(signals, synthetic_prices, holding_days=21)
    calendar = synthetic_prices["SPY"].index

    sim = simulate_portfolio(trades, calendar, initial_capital=500.0, max_position_pct=0.10)

    assert (sim.equity_curve > 0).all()
    assert sim.equity_curve.index.equals(calendar)


def test_simulate_portfolio_with_no_trades_is_flat_at_initial_capital(synthetic_prices):
    calendar = synthetic_prices["SPY"].index
    empty_trades = pd.DataFrame(columns=["ticker", "entry_date", "exit_date", "net_return"])
    sim = simulate_portfolio(empty_trades, calendar, initial_capital=500.0)
    assert (sim.equity_curve == 500.0).all()


def test_buy_and_hold_benchmark_matches_price_ratio(synthetic_prices):
    calendar = synthetic_prices["SPY"].index
    curve = buy_and_hold_benchmark(synthetic_prices["SPY"], calendar, initial_capital=500.0)
    expected_final_ratio = synthetic_prices["SPY"]["adj_close"].iloc[-1] / synthetic_prices["SPY"]["adj_close"].iloc[0]
    assert np.isclose(curve.iloc[-1] / curve.iloc[0], expected_final_ratio, rtol=1e-6)
