"""Performance metrics for an equity curve.

Nothing here is exotic on purpose — CAGR, Sharpe, max drawdown, win rate,
and a benchmark comparison are the minimum set needed to tell a real edge
from noise. Deliberately does *not* produce a single "score" — report all
of them together, since any one metric in isolation is easy to game.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class PerformanceReport:
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    benchmark_total_return: float | None = None
    excess_return_vs_benchmark: float | None = None

    def to_dict(self) -> dict:
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "annualized_volatility": self.annualized_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "n_trades": self.n_trades,
            "benchmark_total_return": self.benchmark_total_return,
            "excess_return_vs_benchmark": self.excess_return_vs_benchmark,
        }


def max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = daily_returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    std = excess.std()
    if std == 0 or pd.isna(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def cagr(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    n_days = (equity_curve.index[-1] - equity_curve.index[0]).days
    if n_days <= 0:
        return 0.0
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    years = n_days / 365.25
    if total_return <= 0:
        return -1.0
    return float(total_return ** (1 / years) - 1)


def build_report(
    equity_curve: pd.Series,
    trades: pd.DataFrame,
    benchmark_equity_curve: pd.Series | None = None,
) -> PerformanceReport:
    daily_returns = equity_curve.pct_change().dropna()
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) if len(equity_curve) > 1 else 0.0

    win_rate = float((trades["net_return"] > 0).mean()) if "net_return" in trades and not trades.empty else 0.0

    benchmark_total_return = None
    excess_return = None
    if benchmark_equity_curve is not None and len(benchmark_equity_curve) > 1:
        benchmark_total_return = float(
            benchmark_equity_curve.iloc[-1] / benchmark_equity_curve.iloc[0] - 1
        )
        excess_return = total_return - benchmark_total_return

    return PerformanceReport(
        total_return=total_return,
        cagr=cagr(equity_curve),
        annualized_volatility=float(daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if not daily_returns.empty else 0.0,
        sharpe_ratio=sharpe_ratio(daily_returns),
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate,
        n_trades=int(len(trades)),
        benchmark_total_return=benchmark_total_return,
        excess_return_vs_benchmark=excess_return,
    )
