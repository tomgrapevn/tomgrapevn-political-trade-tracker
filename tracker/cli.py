"""Command-line entry point.

    python -m tracker.cli fetch-data
    python -m tracker.cli backtest-mirror
    python -m tracker.cli backtest-events
    python -m tracker.cli train-mirror
    python -m tracker.cli paper-trade --strategy mirror

All commands work end-to-end against real free data sources when run
somewhere with open internet access (see README — this sandbox's outbound
network is restricted, so these paths are exercised in tests against
synthetic fixtures instead of live data).
"""

from __future__ import annotations

import logging

import click
import pandas as pd

from tracker.backtest.engine import buy_and_hold_benchmark, resolve_trades, simulate_portfolio
from tracker.backtest.metrics import build_report
from tracker.config import REPORTS_DIR, settings
from tracker.data import disclosures as disclosures_data
from tracker.data import fx
from tracker.data import insider_trades as insider_data
from tracker.data import news as news_data
from tracker.data import prices as prices_data
from tracker.data.event_map import all_tickers as event_tickers
from tracker.models import features as feature_lib
from tracker.models.prediction_engine import train_and_evaluate
from tracker.reporting import render_report, save_report
from tracker.signals import event_driven, mirror_trade

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@click.group()
def cli():
    pass


@cli.command("fetch-data")
@click.option("--force-refresh", is_flag=True, help="Bypass local cache and re-fetch everything.")
def fetch_data(force_refresh: bool):
    """Warm the local cache: disclosures, prices, news."""
    df = disclosures_data.fetch_disclosures(force_refresh=force_refresh)
    click.echo(f"Congress disclosures: {len(df)} rows, {df['ticker'].nunique()} tickers")

    insiders = insider_data.fetch_insider_trades()
    click.echo(f"Insider (Form 4) trades: {len(insiders)} rows for {', '.join(settings.watched_insiders)}")

    tickers = sorted(
        set(df["ticker"].dropna()) | set(insiders["ticker"].dropna()) | set(event_tickers()) | {prices_data.BENCHMARK_TICKER}
    )
    prices = prices_data.fetch_prices(tickers, use_cache=not force_refresh)
    click.echo(f"Prices: fetched {len(prices)}/{len(tickers)} tickers")

    news = news_data.fetch_policy_news(use_cache=not force_refresh)
    click.echo(f"News: {len(news)} articles across {news['keyword'].nunique() if not news.empty else 0} keywords")

    capital_usd, fx_rate = fx.resolve_capital_usd()
    click.echo(f"FX: £{settings.initial_capital_gbp:,.2f} -> ${capital_usd:,.2f} @ {fx_rate:.4f} GBPUSD")


def _mirror_pipeline(holding_days: int, min_lag_days: int | None):
    congress_df = disclosures_data.fetch_disclosures()
    congress_df = disclosures_data.filter_watchlist(congress_df, settings.watchlist)

    insider_df = insider_data.fetch_insider_trades()

    df = pd.concat([congress_df, insider_df], ignore_index=True) if not insider_df.empty else congress_df
    signals = mirror_trade.generate_signals(df)
    if min_lag_days is not None:
        signals = signals[signals["disclosure_lag_days"] >= min_lag_days]

    tickers = sorted(set(signals["ticker"]) | {prices_data.BENCHMARK_TICKER})
    prices = prices_data.fetch_prices(tickers)
    trades = resolve_trades(signals, prices, holding_days=holding_days, transaction_cost_bps=settings.transaction_cost_bps)
    return trades, prices


@cli.command("backtest-mirror")
@click.option("--holding-days", default=21, show_default=True)
@click.option("--min-lag-days", default=None, type=int, help="Drop signals disclosed faster than this (data-quality filter).")
def backtest_mirror(holding_days: int, min_lag_days: int | None):
    """Backtest the 'mirror disclosed Congressional trades' strategy."""
    trades, prices = _mirror_pipeline(holding_days, min_lag_days)
    if trades.empty:
        click.echo("No resolvable trades — check WATCHLIST and data availability.")
        return

    capital_usd, fx_rate = fx.resolve_capital_usd()
    calendar = prices[prices_data.BENCHMARK_TICKER].index
    sim = simulate_portfolio(trades, calendar, initial_capital=capital_usd, max_position_pct=settings.max_position_pct)
    benchmark_curve = buy_and_hold_benchmark(prices[prices_data.BENCHMARK_TICKER], calendar, capital_usd)
    report = build_report(sim.equity_curve, trades, benchmark_curve)
    click.echo(f"Starting capital: £{settings.initial_capital_gbp:,.2f} -> ${capital_usd:,.2f} @ {fx_rate:.4f} GBPUSD")

    breakdown = mirror_trade.member_win_rates(trades)
    content = render_report("Mirror-Trade Strategy Backtest", report, trades, breakdown, "member")
    out_path = REPORTS_DIR / "backtest_mirror.md"
    save_report(content, str(out_path))
    click.echo(content)
    click.echo(f"\nSaved to {out_path}")


def _event_pipeline(holding_days: int, min_article_count: int):
    news = news_data.fetch_policy_news()
    daily = news_data.daily_event_dates(news)
    signals = event_driven.generate_signals(daily, min_article_count=min_article_count)

    tickers = sorted(set(signals["ticker"]) | {prices_data.BENCHMARK_TICKER}) if not signals.empty else [prices_data.BENCHMARK_TICKER]
    prices = prices_data.fetch_prices(tickers)
    trades = resolve_trades(signals, prices, holding_days=holding_days, transaction_cost_bps=settings.transaction_cost_bps)
    return trades, prices


@cli.command("backtest-events")
@click.option("--holding-days", default=10, show_default=True)
@click.option("--min-article-count", default=3, show_default=True)
def backtest_events(holding_days: int, min_article_count: int):
    """Backtest the 'react to policy/news events' strategy."""
    trades, prices = _event_pipeline(holding_days, min_article_count)
    if trades.empty:
        click.echo("No resolvable trades — check event_map.py keywords and news availability.")
        return

    capital_usd, fx_rate = fx.resolve_capital_usd()
    calendar = prices[prices_data.BENCHMARK_TICKER].index
    sim = simulate_portfolio(trades, calendar, initial_capital=capital_usd, max_position_pct=settings.max_position_pct)
    benchmark_curve = buy_and_hold_benchmark(prices[prices_data.BENCHMARK_TICKER], calendar, capital_usd)
    report = build_report(sim.equity_curve, trades, benchmark_curve)
    click.echo(f"Starting capital: £{settings.initial_capital_gbp:,.2f} -> ${capital_usd:,.2f} @ {fx_rate:.4f} GBPUSD")

    breakdown = event_driven.category_hit_rates(trades)
    content = render_report("Event-Driven Strategy Backtest", report, trades, breakdown, "category")
    out_path = REPORTS_DIR / "backtest_events.md"
    save_report(content, str(out_path))
    click.echo(content)
    click.echo(f"\nSaved to {out_path}")


@cli.command("train-mirror")
@click.option("--model-type", default="gbm", type=click.Choice(["gbm", "logreg"]))
@click.option("--holding-days", default=21, show_default=True)
def train_mirror(model_type: str, holding_days: int):
    """Train + chronologically evaluate the mirror-trade prediction engine."""
    trades, _ = _mirror_pipeline(holding_days, None)
    if len(trades) < 20:
        click.echo(f"Only {len(trades)} resolved trades — need more history/watchlist coverage to train meaningfully.")
        return
    X, y = feature_lib.build_mirror_features(trades)
    _, report = train_and_evaluate(X, y, trades["signal_date"], model_type=model_type)
    click.echo(report.to_dict())


@cli.command("train-events")
@click.option("--model-type", default="gbm", type=click.Choice(["gbm", "logreg"]))
@click.option("--holding-days", default=10, show_default=True)
@click.option("--min-article-count", default=3, show_default=True)
def train_events(model_type: str, holding_days: int, min_article_count: int):
    """Train + chronologically evaluate the event-driven prediction engine."""
    trades, _ = _event_pipeline(holding_days, min_article_count)
    if len(trades) < 20:
        click.echo(f"Only {len(trades)} resolved trades — need more history/keyword coverage to train meaningfully.")
        return
    X, y = feature_lib.build_event_features(trades)
    _, report = train_and_evaluate(X, y, trades["signal_date"], model_type=model_type)
    click.echo(report.to_dict())


@cli.command("backtest-walkforward")
@click.option("--strategy", type=click.Choice(["mirror", "events"]), required=True)
@click.option("--train-months", default=6, show_default=True)
@click.option("--test-months", default=1, show_default=True)
@click.option("--model-type", default="gbm", type=click.Choice(["gbm", "logreg"]))
@click.option("--prob-threshold", default=0.5, show_default=True)
@click.option("--holding-days", default=None, type=int)
def backtest_walkforward(
    strategy: str, train_months: int, test_months: int, model_type: str, prob_threshold: float, holding_days: int | None
):
    """Honest out-of-sample test: roll the model forward one test block at
    a time, training only on data that predates it, and only take trades
    it scores >= --prob-threshold. Reports the model-filtered curve next to
    a take-every-signal curve and buy-and-hold, so you can see whether the
    model is adding anything over just mirroring everything. This is
    deliberately not a parameter search against the full history — see
    tracker/backtest/walkforward.py for why."""
    from tracker.backtest.walkforward import walk_forward_backtest

    if strategy == "mirror":
        hd = holding_days or 21
        trades, prices = _mirror_pipeline(hd, None)
        build_features_fn = feature_lib.build_mirror_features
        label = "Mirror-Trade"
    else:
        hd = holding_days or 10
        trades, prices = _event_pipeline(hd, 3)
        build_features_fn = feature_lib.build_event_features
        label = "Event-Driven"

    if trades.empty:
        click.echo("No resolvable trades to walk-forward over.")
        return

    result = walk_forward_backtest(
        trades,
        build_features_fn,
        train_months=train_months,
        test_months=test_months,
        model_type=model_type,
        prob_threshold=prob_threshold,
    )
    click.echo(result.fold_summary().to_string(index=False))

    if result.all_candidate_trades.empty:
        click.echo("No out-of-sample test folds had enough training data — need a longer history or a lower --train-months.")
        return

    capital_usd, fx_rate = fx.resolve_capital_usd()
    click.echo(f"\nStarting capital: £{settings.initial_capital_gbp:,.2f} -> ${capital_usd:,.2f} @ {fx_rate:.4f} GBPUSD")

    calendar = prices[prices_data.BENCHMARK_TICKER].index
    oos_start = result.all_candidate_trades["signal_date"].min()
    calendar = calendar[calendar >= oos_start]
    benchmark_curve = buy_and_hold_benchmark(prices[prices_data.BENCHMARK_TICKER], calendar, capital_usd)

    for title, trade_set in (
        ("Model-filtered (out-of-sample)", result.taken_trades),
        ("Take every signal (out-of-sample)", result.all_candidate_trades),
    ):
        sim = simulate_portfolio(trade_set, calendar, initial_capital=capital_usd, max_position_pct=settings.max_position_pct)
        report = build_report(sim.equity_curve, trade_set, benchmark_curve)
        click.echo(f"\n=== {label}: {title} ===")
        click.echo(report.to_dict())


@cli.command("paper-trade")
@click.option("--strategy", type=click.Choice(["mirror", "events"]), required=True)
@click.option("--holding-days", default=21, show_default=True)
@click.option("--confirm", is_flag=True, help="Actually submit to the paper API instead of a dry run.")
def paper_trade(strategy: str, holding_days: int, confirm: bool):
    """Size the most recent signals against your Alpaca *paper* account and
    submit them (or just print them, without --confirm)."""
    from tracker.execution.paper_broker import client_from_settings, execute_orders, signals_to_orders

    if strategy == "mirror":
        congress_df = disclosures_data.fetch_disclosures()
        congress_df = disclosures_data.filter_watchlist(congress_df, settings.watchlist)
        insider_df = insider_data.fetch_insider_trades()
        df = pd.concat([congress_df, insider_df], ignore_index=True) if not insider_df.empty else congress_df
        signals = mirror_trade.generate_signals(df)
    else:
        news = news_data.fetch_policy_news()
        daily = news_data.daily_event_dates(news)
        signals = event_driven.generate_signals(daily)

    if signals.empty:
        click.echo("No current signals to trade.")
        return

    client = client_from_settings()
    account = client.get_account()
    equity = float(account["equity"])
    orders = signals_to_orders(signals, equity, settings.max_position_pct)

    click.echo(f"Paper account equity: ${equity:,.2f}")
    click.echo(orders.to_string(index=False))

    results = execute_orders(client, orders, dry_run=not confirm)
    for r in results:
        click.echo(r)


@cli.command("daily-run")
@click.option("--window-hours", default=24, show_default=True, help="How far back to look for news/disclosures.")
@click.option("--min-article-count", default=3, show_default=True)
@click.option("--confirm", is_flag=True, help="Actually submit to the paper API instead of a dry run.")
def daily_run_cmd(window_hours: int, min_article_count: int, confirm: bool):
    """Run once: react to the last `window_hours` of news + newly disclosed
    trades, size against GBP capital, submit to the paper broker (dry run
    unless --confirm). Intended to be invoked by an external daily
    scheduler — see README "Daily automation"."""
    from tracker.pipeline.daily import run_daily

    result = run_daily(window_hours=window_hours, min_article_count=min_article_count, dry_run=not confirm)
    click.echo(result.summary())
    if not result.orders.empty:
        click.echo(result.orders.to_string(index=False))
    for r in result.order_results:
        click.echo(r)


if __name__ == "__main__":
    cli()
