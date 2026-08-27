import numpy as np
import pandas as pd

from tracker.backtest.metrics import build_report, cagr, max_drawdown, sharpe_ratio


def test_cagr_doubles_in_one_year():
    dates = pd.bdate_range("2024-01-01", periods=252)
    equity = pd.Series(np.linspace(100, 200, len(dates)), index=dates)
    assert 0.9 < cagr(equity) < 1.1  # ~100% annualized, allow for trading-day/calendar-day slack


def test_max_drawdown_detects_known_drop():
    equity = pd.Series([100, 120, 60, 90, 150])
    # peak 120 -> trough 60 = -50%
    assert np.isclose(max_drawdown(equity), -0.5)


def test_sharpe_ratio_zero_for_zero_variance_returns():
    returns = pd.Series([0.001] * 100)
    # Non-zero mean, but std==0 after removing the (tiny) risk-free drag would
    # normally divide by zero — sharpe_ratio must not raise or return NaN/inf.
    result = sharpe_ratio(returns)
    assert np.isfinite(result)


def test_build_report_win_rate_matches_trade_log():
    dates = pd.bdate_range("2024-01-01", periods=10)
    equity = pd.Series(np.linspace(500, 550, len(dates)), index=dates)
    trades = pd.DataFrame({"net_return": [0.05, -0.02, 0.01, -0.01]})
    report = build_report(equity, trades)
    assert np.isclose(report.win_rate, 0.5)
    assert report.n_trades == 4


def test_build_report_excess_return_vs_benchmark():
    dates = pd.bdate_range("2024-01-01", periods=10)
    equity = pd.Series(np.linspace(500, 600, len(dates)), index=dates)
    benchmark = pd.Series(np.linspace(500, 550, len(dates)), index=dates)
    trades = pd.DataFrame({"net_return": [0.1]})
    report = build_report(equity, trades, benchmark)
    assert report.excess_return_vs_benchmark > 0
