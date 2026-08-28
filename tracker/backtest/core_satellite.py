"""Core + satellite portfolio simulation: stay fully invested in a
benchmark, fund tactical tilts by temporarily selling benchmark units
rather than by holding cash between signals.

Why this exists: `tracker.backtest.engine.simulate_portfolio` sizes each
position as a % of equity and leaves the rest in cash — appropriate for a
"small speculative pot," but it means a strategy earns its edge (if any)
*instead of* the market's own return, not on top of it. Over a period
where the benchmark itself returns +20-40%, a strategy that's 90% in cash
the whole time structurally can't compete even with a genuinely good
signal (see README "Core + satellite: beating the fund, not just the
signal" for the real numbers this produced).

This module tests the other design: 100% of capital sits in the benchmark
by default; a validated signal temporarily reallocates a slice of that
into the tilt, and the proceeds (gain or loss) return to the benchmark
when the tilt closes. The result answers "does layering this signal on
top of just holding the fund beat holding the fund alone" — a different,
usually more realistic question than "does this signal beat the fund on
its own."
"""

from __future__ import annotations

import pandas as pd

from tracker.backtest.engine import SimulationResult


def simulate_core_satellite(
    trades: pd.DataFrame,
    benchmark_prices: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
    initial_capital: float = 500.0,
    satellite_pct: float = 0.15,
    price_col: str = "adj_close",
) -> SimulationResult:
    """`trades` is the output of tracker.backtest.engine.resolve_trades
    (needs ticker, entry_date, exit_date, net_return). `benchmark_prices`
    is a single ticker's OHLCV frame (e.g. from tracker.data.prices).

    Each new signal reallocates `satellite_pct` of *current total equity*
    from core benchmark units into the tilt; proceeds (including the
    tilt's gain or loss) buy back into the core when it closes. A ticker
    already held is skipped until its position closes — same rule as
    `simulate_portfolio`.
    """
    core_price = benchmark_prices[price_col].reindex(trading_calendar).ffill().bfill()

    if trades.empty or core_price.empty:
        equity = pd.Series(initial_capital, index=trading_calendar)
        if not core_price.empty and core_price.iloc[0] > 0:
            units = initial_capital / core_price.iloc[0]
            equity = core_price * units
        return SimulationResult(equity_curve=equity, trades=trades)

    trades = trades.sort_values("entry_date").reset_index(drop=True)
    core_units = initial_capital / core_price.iloc[0]

    open_positions: list[dict] = []
    open_tickers: set[str] = set()
    equity_points = []

    trades_by_entry = trades.groupby("entry_date")
    trades_by_exit = trades.groupby("exit_date")

    for day in trading_calendar:
        day_price = core_price.loc[day]

        if day in trades_by_exit.groups:
            for _, trade in trades_by_exit.get_group(day).iterrows():
                match = next(
                    (p for p in open_positions if p["ticker"] == trade["ticker"] and p["entry_date"] == trade["entry_date"]),
                    None,
                )
                if match is not None:
                    proceeds = match["capital"] * (1 + trade["net_return"])
                    if day_price > 0:
                        core_units += proceeds / day_price
                    open_positions.remove(match)
                    open_tickers.discard(trade["ticker"])

        if day in trades_by_entry.groups:
            for _, trade in trades_by_entry.get_group(day).iterrows():
                if trade["ticker"] in open_tickers or day_price <= 0:
                    continue
                current_equity = core_units * day_price + sum(p["capital"] for p in open_positions)
                allocation = satellite_pct * current_equity
                if allocation <= 0:
                    continue
                core_units -= allocation / day_price
                open_positions.append(
                    {
                        "ticker": trade["ticker"],
                        "entry_date": trade["entry_date"],
                        "exit_date": trade["exit_date"],
                        "capital": allocation,
                        "net_return": trade["net_return"],
                    }
                )
                open_tickers.add(trade["ticker"])

        satellite_value = 0.0
        for p in open_positions:
            total_days = max((p["exit_date"] - p["entry_date"]).days, 1)
            elapsed_days = max((day - p["entry_date"]).days, 0)
            progress = min(elapsed_days / total_days, 1.0)
            satellite_value += p["capital"] * (1 + p["net_return"] * progress)

        equity_points.append(core_units * day_price + satellite_value)

    equity_curve = pd.Series(equity_points, index=trading_calendar, name="equity")
    return SimulationResult(equity_curve=equity_curve, trades=trades)
