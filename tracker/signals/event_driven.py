"""Signal generator: react to policy/geopolitical news via tracker.data.event_map.

A "signal" fires on a day where article volume for a mapped keyword crosses
`min_article_count` — a crude but simple proxy for "this became a real news
event" rather than one wire story nobody read.
"""

from __future__ import annotations

import pandas as pd

from tracker.data.event_map import rules_by_keyword


def generate_signals(daily_events: pd.DataFrame, min_article_count: int = 3) -> pd.DataFrame:
    """`daily_events` is the output of tracker.data.news.daily_event_dates:
    one row per (date, keyword, article_count).

    Returns one row per (signal_date, ticker, side, category) — a keyword
    day can expand into multiple tickers/categories per tracker.data.event_map.
    """
    if daily_events.empty:
        return pd.DataFrame(
            columns=["signal_date", "ticker", "side", "category", "keyword", "article_count", "rationale"]
        )

    rules_map = rules_by_keyword()
    triggered = daily_events[daily_events["article_count"] >= min_article_count]

    rows = []
    for _, event in triggered.iterrows():
        for rule in rules_map.get(str(event["keyword"]).lower(), []):
            for ticker in rule.tickers:
                rows.append(
                    {
                        "signal_date": event["date"],
                        "ticker": ticker,
                        "side": rule.direction,
                        "category": rule.category,
                        "keyword": rule.keyword,
                        "article_count": event["article_count"],
                        "rationale": rule.rationale,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=["signal_date", "ticker", "side", "category", "keyword", "article_count", "rationale"]
        )
    return pd.DataFrame(rows).sort_values("signal_date").reset_index(drop=True)


def category_hit_rates(signals_with_outcomes: pd.DataFrame) -> pd.DataFrame:
    """Same idea as mirror_trade.member_win_rates, grouped by event
    category instead of by member — which policy themes actually produced
    a tradeable edge historically, versus which are noise."""
    df = signals_with_outcomes.dropna(subset=["forward_return"])
    if df.empty:
        return pd.DataFrame(columns=["category", "n_signals", "win_rate", "avg_forward_return"])
    grouped = df.groupby("category")["forward_return"]
    return (
        grouped.agg(
            n_signals="count",
            win_rate=lambda s: (s > 0).mean(),
            avg_forward_return="mean",
        )
        .reset_index()
        .sort_values("avg_forward_return", ascending=False)
    )
