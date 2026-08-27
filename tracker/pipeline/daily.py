"""Daily pipeline: react to the last `window_hours` of news + newly
disclosed trades, size against GBP capital, submit to the paper broker.

Meant to be invoked once a day by an external scheduler (cron / a Claude
Code Routine / anything that can run a shell command on a schedule) —
`python -m tracker.cli daily-run`. This module has no scheduler of its own;
"7am UK time" is handled by whatever fires this, not by code in here (see
README "Daily automation" for the UK-DST caveat on a fixed-UTC cron).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from tracker.config import settings
from tracker.data import disclosures as disclosures_data
from tracker.data import fx
from tracker.data import insider_trades as insider_data
from tracker.data import news as news_data
from tracker.execution.paper_broker import client_from_settings, execute_orders, signals_to_orders
from tracker.signals import event_driven, mirror_trade

logger = logging.getLogger(__name__)

_ORDER_COLS = ["signal_date", "ticker", "side"]


@dataclass
class DailyRunResult:
    as_of: pd.Timestamp
    window_start: pd.Timestamp
    news_articles: int
    event_signals: pd.DataFrame
    trade_signals: pd.DataFrame
    orders: pd.DataFrame
    order_results: list
    capital_usd: float
    fx_rate: float

    def summary(self) -> dict:
        return {
            "as_of": str(self.as_of),
            "window_start": str(self.window_start),
            "news_articles": self.news_articles,
            "n_event_signals": int(len(self.event_signals)),
            "n_trade_signals": int(len(self.trade_signals)),
            "n_orders": int(len(self.orders)),
            "capital_usd": round(self.capital_usd, 2),
            "fx_rate": self.fx_rate,
        }


def _recent_trade_signals(window_start: pd.Timestamp, as_of: pd.Timestamp) -> pd.DataFrame:
    congress_df = disclosures_data.fetch_disclosures()
    congress_df = disclosures_data.filter_watchlist(congress_df, settings.watchlist)

    insider_df = insider_data.fetch_insider_trades()

    combined = pd.concat([congress_df, insider_df], ignore_index=True) if not insider_df.empty else congress_df
    if combined.empty:
        return combined

    in_window = combined["disclosure_date"].between(window_start, as_of)
    return mirror_trade.generate_signals(combined[in_window])


def _recent_event_signals(window_start: pd.Timestamp, as_of: pd.Timestamp, min_article_count: int) -> pd.DataFrame:
    news = news_data.fetch_policy_news(start=window_start.to_pydatetime(), end=as_of.to_pydatetime())
    daily_events = news_data.daily_event_dates(news)
    return event_driven.generate_signals(daily_events, min_article_count=min_article_count), len(news)


def run_daily(
    as_of: pd.Timestamp | None = None,
    window_hours: int = 24,
    min_article_count: int = 3,
    dry_run: bool = True,
) -> DailyRunResult:
    as_of = pd.Timestamp.utcnow().tz_localize(None) if as_of is None else pd.Timestamp(as_of)
    window_start = as_of - pd.Timedelta(hours=window_hours)

    event_signals, n_articles = _recent_event_signals(window_start, as_of, min_article_count)
    trade_signals = _recent_trade_signals(window_start, as_of)

    capital_usd, fx_rate = fx.resolve_capital_usd()

    frames = [df[_ORDER_COLS] for df in (event_signals, trade_signals) if not df.empty]
    all_signals = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_ORDER_COLS)

    orders = (
        signals_to_orders(all_signals, capital_usd, settings.max_position_pct)
        if not all_signals.empty
        else pd.DataFrame(columns=["ticker", "side", "notional_usd"])
    )

    order_results: list = []
    if not orders.empty:
        if settings.alpaca_api_key and settings.alpaca_secret_key:
            client = client_from_settings()
            order_results = execute_orders(client, orders, dry_run=dry_run)
        else:
            logger.info("No Alpaca paper keys configured in .env — logging signals only, nothing submitted.")
            order_results = [{**row, "status": "logged_only_no_broker_configured"} for row in orders.to_dict("records")]

    return DailyRunResult(
        as_of=as_of,
        window_start=window_start,
        news_articles=n_articles,
        event_signals=event_signals,
        trade_signals=trade_signals,
        orders=orders,
        order_results=order_results,
        capital_usd=capital_usd,
        fx_rate=fx_rate,
    )
