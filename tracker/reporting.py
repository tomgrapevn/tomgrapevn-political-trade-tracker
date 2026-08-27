"""Markdown report generation for a backtest run."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from tracker.backtest.metrics import PerformanceReport

DISCLAIMER = """
> **Not financial advice. Past performance does not predict future results.**
> This report is the output of a backtest against historical data with the
> simplifications documented in `tracker/backtest/engine.py` (no margin
> modeling, flat transaction cost assumption, a 45-day+ real-world
> disclosure lag already baked into the signal timing). Small differences
> in assumptions can flip a backtest from profitable to unprofitable.
> Trading on these signals with real money can lose some or all of the
> capital involved. Nothing in this repository places a live order — see
> `tracker/execution/paper_broker.py`.
"""


def _fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.2%}"


def render_report(
    title: str,
    report: PerformanceReport,
    trades: pd.DataFrame,
    breakdown: pd.DataFrame | None = None,
    breakdown_label: str = "member",
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {title}",
        "",
        f"_Generated {generated}_",
        DISCLAIMER,
        "## Performance summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total return | {_fmt_pct(report.total_return)} |",
        f"| CAGR | {_fmt_pct(report.cagr)} |",
        f"| Annualized volatility | {_fmt_pct(report.annualized_volatility)} |",
        f"| Sharpe ratio | {report.sharpe_ratio:.2f} |",
        f"| Max drawdown | {_fmt_pct(report.max_drawdown)} |",
        f"| Win rate (per trade) | {_fmt_pct(report.win_rate)} |",
        f"| Number of trades | {report.n_trades} |",
        f"| Benchmark (SPY buy & hold) total return | {_fmt_pct(report.benchmark_total_return)} |",
        f"| Excess return vs. benchmark | {_fmt_pct(report.excess_return_vs_benchmark)} |",
        "",
    ]

    if breakdown is not None and not breakdown.empty:
        lines += [f"## Breakdown by {breakdown_label}", "", breakdown.to_markdown(index=False), ""]

    if not trades.empty:
        lines += [
            "## Trade log (most recent 25)",
            "",
            trades.sort_values("entry_date", ascending=False)
            .head(25)
            .to_markdown(index=False),
            "",
        ]

    return "\n".join(lines)


def save_report(content: str, path: str) -> None:
    from pathlib import Path

    Path(path).write_text(content)
