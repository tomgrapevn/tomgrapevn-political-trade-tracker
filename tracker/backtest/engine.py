"""Event-driven backtest engine.

Two stages:

1. `resolve_trades` turns each signal row into a concrete trade: entry price
   (first close on/after signal_date), exit price (close `holding_days`
   trading days later), and a net return after round-trip transaction costs.
   This is what tracker.signals.*.member_win_rates / category_hit_rates
   consume.

2. `simulate_portfolio` walks the trades through time against a capital
   constraint (starting capital, max position size as a % of equity) to
   produce a day-by-day equity curve — the thing Sharpe/drawdown/CAGR are
   computed from.

Simplifications, stated up front rather than hidden in the numbers: no
margin/borrow modeling for shorts (a short's return is just the sign-flipped
long return), no slippage beyond the flat `transaction_cost_bps`, and
positions never overlap-average — a new signal on a ticker you already hold
is skipped until the existing position closes. This is a research tool, not
a broker simulator; treat results as directional, not exact.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

_SIDE_SIGN = {"long": 1.0, "short": -1.0}


def _next_close_on_or_after(prices: pd.DataFrame, date: pd.Timestamp, price_col: str = "adj_close"):
    idx = prices.index[prices.index >= date]
    if len(idx) == 0:
        return None, None
    pos = prices.index.get_loc(idx[0])
    return idx[0], float(prices[price_col].iloc[pos])


def resolve_trades(
    signals: pd.DataFrame,
    prices_by_ticker: dict[str, pd.DataFrame],
    holding_days: int = 21,
    transaction_cost_bps: float = 5.0,
    price_col: str = "adj_close",
) -> pd.DataFrame:
    """Resolve each signal into an entry/exit price pair and a return.

    Adds columns: entry_date, entry_price, exit_date, exit_price,
    gross_return, net_return, forward_return (alias of net_return, for the
    win-rate helpers in tracker.signals).
    """
    if signals.empty:
        return signals.assign(
            entry_date=pd.Series(dtype="datetime64[ns]"),
            entry_price=pd.Series(dtype=float),
            exit_date=pd.Series(dtype="datetime64[ns]"),
            exit_price=pd.Series(dtype=float),
            gross_return=pd.Series(dtype=float),
            net_return=pd.Series(dtype=float),
            forward_return=pd.Series(dtype=float),
        )

    round_trip_cost = 2 * transaction_cost_bps / 10_000.0
    rows = []
    for _, sig in signals.iterrows():
        prices = prices_by_ticker.get(sig["ticker"])
        if prices is None or prices.empty:
            continue

        entry_date, entry_price = _next_close_on_or_after(prices, pd.Timestamp(sig["signal_date"]), price_col)
        if entry_date is None:
            continue

        entry_pos = prices.index.get_loc(entry_date)
        exit_pos = entry_pos + holding_days
        if exit_pos >= len(prices):
            continue
        exit_date = prices.index[exit_pos]
        exit_price = float(prices[price_col].iloc[exit_pos])

        sign = _SIDE_SIGN.get(sig["side"], 1.0)
        gross_return = sign * (exit_price / entry_price - 1.0)
        net_return = gross_return - round_trip_cost

        row = sig.to_dict()
        row.update(
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            gross_return=gross_return,
            net_return=net_return,
            forward_return=net_return,
        )
        rows.append(row)

    return pd.DataFrame(rows)


@dataclass
class SimulationResult:
    equity_curve: pd.Series
    trades: pd.DataFrame


def simulate_portfolio(
    trades: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
    initial_capital: float = 500.0,
    max_position_pct: float = 0.10,
) -> SimulationResult:
    """Simulate capital allocation across resolved trades (see
    `resolve_trades`) over `trading_calendar`.

    Position sizing: each new position gets min(max_position_pct * current
    equity, available cash). A ticker with an already-open position is
    skipped until it closes — no averaging in. Equity is marked to market
    daily by linearly accruing each open position's realized trade return
    over its holding period (a simplification for tickers where we don't
    keep the full daily price series in memory here; see engine tests for
    how close this tracks a true daily mark for typical horizons).
    """
    if trades.empty:
        equity = pd.Series(initial_capital, index=trading_calendar)
        return SimulationResult(equity_curve=equity, trades=trades)

    trades = trades.sort_values("entry_date").reset_index(drop=True)

    cash = initial_capital
    open_positions: list[dict] = []
    equity_points = []

    trades_by_entry = trades.groupby("entry_date")
    trades_by_exit = trades.groupby("exit_date")
    open_tickers: set[str] = set()

    for day in trading_calendar:
        if day in trades_by_exit.groups:
            for _, trade in trades_by_exit.get_group(day).iterrows():
                match = next((p for p in open_positions if p["ticker"] == trade["ticker"] and p["entry_date"] == trade["entry_date"]), None)
                if match is not None:
                    cash += match["capital"] * (1 + trade["net_return"])
                    open_positions.remove(match)
                    open_tickers.discard(trade["ticker"])

        if day in trades_by_entry.groups:
            for _, trade in trades_by_entry.get_group(day).iterrows():
                if trade["ticker"] in open_tickers:
                    continue
                current_equity = cash + sum(p["capital"] for p in open_positions)
                allocation = min(max_position_pct * current_equity, cash)
                if allocation <= 0:
                    continue
                cash -= allocation
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

        mark_to_market = 0.0
        for p in open_positions:
            total_days = max((p["exit_date"] - p["entry_date"]).days, 1)
            elapsed_days = max((day - p["entry_date"]).days, 0)
            progress = min(elapsed_days / total_days, 1.0)
            mark_to_market += p["capital"] * (1 + p["net_return"] * progress)

        equity_points.append(cash + mark_to_market)

    equity_curve = pd.Series(equity_points, index=trading_calendar, name="equity")
    return SimulationResult(equity_curve=equity_curve, trades=trades)


def buy_and_hold_benchmark(
    benchmark_prices: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
    initial_capital: float = 500.0,
    price_col: str = "adj_close",
) -> pd.Series:
    """Equity curve for putting the full initial capital into the benchmark
    (default SPY) on day one and holding — the bar the strategy has to
    clear to have been worth doing."""
    aligned = benchmark_prices[price_col].reindex(trading_calendar).ffill().bfill()
    if aligned.empty or aligned.iloc[0] == 0:
        return pd.Series(initial_capital, index=trading_calendar)
    shares = initial_capital / aligned.iloc[0]
    return (aligned * shares).rename("benchmark_equity")
