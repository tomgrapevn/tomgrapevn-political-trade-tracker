import numpy as np
import pandas as pd

from tracker.backtest.core_satellite import simulate_core_satellite


def _flat_benchmark(calendar: pd.DatetimeIndex, price: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({"adj_close": price}, index=calendar)


def _rising_benchmark(calendar: pd.DatetimeIndex, daily_return: float = 0.001) -> pd.DataFrame:
    prices = 100 * np.cumprod([1 + daily_return] * len(calendar))
    return pd.DataFrame({"adj_close": prices}, index=calendar)


def test_no_trades_tracks_benchmark_exactly(synthetic_prices):
    calendar = synthetic_prices["SPY"].index
    sim = simulate_core_satellite(pd.DataFrame(columns=["ticker", "entry_date", "exit_date", "net_return"]), synthetic_prices["SPY"], calendar, initial_capital=500.0)
    ratio = synthetic_prices["SPY"]["adj_close"] / synthetic_prices["SPY"]["adj_close"].iloc[0]
    expected = 500.0 * ratio
    assert np.allclose(sim.equity_curve.values, expected.values, rtol=1e-6)


def test_stays_fully_invested_never_holds_idle_cash():
    calendar = pd.bdate_range("2024-01-01", periods=60)
    benchmark = _flat_benchmark(calendar)
    trades = pd.DataFrame(
        {
            "ticker": ["XLE"],
            "entry_date": [calendar[10]],
            "exit_date": [calendar[20]],
            "net_return": [0.05],
        }
    )
    sim = simulate_core_satellite(trades, benchmark, calendar, initial_capital=1000.0, satellite_pct=0.20)
    # with a flat benchmark, equity should never dip below what a losing
    # satellite trade could cost, and should reflect the full +5% gain on
    # the allocated slice once the trade closes (rather than sitting idle)
    assert sim.equity_curve.iloc[-1] > sim.equity_curve.iloc[0]
    assert (sim.equity_curve > 0).all()


def test_winning_tilt_beats_pure_benchmark_holding():
    calendar = pd.bdate_range("2024-01-01", periods=60)
    benchmark = _rising_benchmark(calendar, daily_return=0.0005)
    trades = pd.DataFrame(
        {
            "ticker": ["XLE"],
            "entry_date": [calendar[5]],
            "exit_date": [calendar[15]],
            "net_return": [0.20],  # a big win on the tilt
        }
    )
    sim = simulate_core_satellite(trades, benchmark, calendar, initial_capital=1000.0, satellite_pct=0.15)
    pure_benchmark_final = 1000.0 * benchmark["adj_close"].iloc[-1] / benchmark["adj_close"].iloc[0]
    assert sim.equity_curve.iloc[-1] > pure_benchmark_final


def test_losing_tilt_still_keeps_most_of_benchmark_exposure():
    calendar = pd.bdate_range("2024-01-01", periods=60)
    benchmark = _rising_benchmark(calendar, daily_return=0.0005)
    trades = pd.DataFrame(
        {
            "ticker": ["XLE"],
            "entry_date": [calendar[5]],
            "exit_date": [calendar[15]],
            "net_return": [-0.20],  # a big loss on the tilt
        }
    )
    sim = simulate_core_satellite(trades, benchmark, calendar, initial_capital=1000.0, satellite_pct=0.15)
    pure_benchmark_final = 1000.0 * benchmark["adj_close"].iloc[-1] / benchmark["adj_close"].iloc[0]
    # a -20% loss on only 15% of the book should cost ~3%, not wipe out gains
    assert sim.equity_curve.iloc[-1] < pure_benchmark_final
    assert sim.equity_curve.iloc[-1] > pure_benchmark_final * 0.9


def test_skips_new_signal_for_ticker_already_open():
    calendar = pd.bdate_range("2024-01-01", periods=60)
    benchmark = _flat_benchmark(calendar)
    trades = pd.DataFrame(
        {
            "ticker": ["XLE", "XLE"],
            "entry_date": [calendar[5], calendar[8]],
            "exit_date": [calendar[20], calendar[25]],
            "net_return": [0.10, -0.50],
        }
    )
    sim = simulate_core_satellite(trades, benchmark, calendar, initial_capital=1000.0, satellite_pct=0.15)
    # the second (disastrous) signal on the same still-open ticker must be
    # ignored — final equity should reflect only the first trade's +10%
    # on its allocated slice, not both
    assert sim.equity_curve.iloc[-1] > 1000.0
