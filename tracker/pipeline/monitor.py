"""Orchestrates the live news monitor: fetch RSS -> match against
tracker/data/live_rules.py -> track open positions so we can remind about
the exit -> return everything needed for an email/notification.

Run via `python -m tracker.cli monitor-news`, on whatever schedule you
wire up (see README "Live monitoring"). Stateless between processes aside
from the on-disk state file (tracker/data/cache/rss_monitor_state.json) —
safe to run from a fresh process each time (e.g. a scheduled trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from tracker.data.live_rules import LiveRule, match_rules
from tracker.data.rss_monitor import Article, fetch_all_feeds, filter_new_articles, load_state, save_state


@dataclass
class NewAlert:
    article: Article
    rule: LiveRule


@dataclass
class ExitReminder:
    category: str
    fired_at: str
    note: str


@dataclass
class MonitorResult:
    checked_at: datetime
    n_articles_fetched: int
    n_articles_new: int
    new_alerts: list[NewAlert] = field(default_factory=list)
    exit_reminders: list[ExitReminder] = field(default_factory=list)

    def has_anything_to_report(self) -> bool:
        return bool(self.new_alerts or self.exit_reminders)


def run_monitor_check() -> MonitorResult:
    state = load_state()
    now = datetime.now(timezone.utc)

    articles = fetch_all_feeds()
    new_articles = filter_new_articles(articles, state)

    new_alerts: list[NewAlert] = []
    seen_categories_this_run: set[str] = set()
    for article in new_articles:
        text = f"{article.title} {article.description}"
        for rule in match_rules(text):
            # one alert per category per run — several headlines about the
            # same event shouldn't fire the same "buy" instruction repeatedly
            if rule.category in seen_categories_this_run:
                continue
            new_alerts.append(NewAlert(article=article, rule=rule))
            seen_categories_this_run.add(rule.category)
            if rule.validated:
                exit_date = pd.Timestamp(now.date()) + pd.tseries.offsets.BDay(rule.holding_days)
                state.setdefault("open_signals", []).append(
                    {
                        "category": rule.category,
                        "fired_at": now.isoformat(),
                        "exit_date": exit_date.isoformat(),
                        "tickers_long": list(rule.tickers_long),
                        "tickers_short": list(rule.tickers_short),
                    }
                )

    exit_reminders: list[ExitReminder] = []
    still_open = []
    today = pd.Timestamp(now.date())
    for signal in state.get("open_signals", []):
        exit_date = pd.Timestamp(signal["exit_date"])
        if exit_date.tzinfo is not None:
            exit_date = exit_date.tz_localize(None)
        if exit_date <= today:
            tickers = ", ".join(signal.get("tickers_long", []) + [f"short {t}" for t in signal.get("tickers_short", [])])
            exit_reminders.append(
                ExitReminder(
                    category=signal["category"],
                    fired_at=signal["fired_at"],
                    note=f"Documented holding period ({signal['category']}) has elapsed for the position opened on {signal['fired_at'][:10]} ({tickers}). Per the backtested rule, consider closing it now.",
                )
            )
        else:
            still_open.append(signal)
    state["open_signals"] = still_open

    save_state(state)

    return MonitorResult(
        checked_at=now,
        n_articles_fetched=len(articles),
        n_articles_new=len(new_articles),
        new_alerts=new_alerts,
        exit_reminders=exit_reminders,
    )


def format_email_body(result: MonitorResult) -> str:
    lines = [
        f"Political trade tracker — live monitor check at {result.checked_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"({result.n_articles_fetched} articles fetched, {result.n_articles_new} new since last check)",
        "",
        "This is an automated keyword match against RSS headlines, not a verified event —",
        "the backtested calendars in this repo were hand-checked against multiple sources;",
        "this alert wasn't. Treat it as 'worth a look', not confirmed. Not financial advice.",
        "",
    ]

    validated = [a for a in result.new_alerts if a.rule.validated]
    informational = [a for a in result.new_alerts if not a.rule.validated]

    if validated:
        lines.append("=== POSSIBLE TRADE SIGNAL (per the documented, backtested rule) ===")
        for alert in validated:
            r = alert.rule
            lines += [
                f"- [{r.category}] {alert.article.title}",
                f"  Source: {alert.article.source} | {alert.article.link}",
                f"  Rule says: long {', '.join(r.tickers_long) or '(none)'}"
                + (f", short {', '.join(r.tickers_short)}" if r.tickers_short else "")
                + f", hold ~{r.holding_days} trading days",
                f"  {r.note}",
                "",
            ]

    if informational:
        lines.append("=== DETECTED BUT NOT A VALIDATED SIGNAL (FYI only) ===")
        for alert in informational:
            lines += [
                f"- [{alert.rule.category}] {alert.article.title}",
                f"  Source: {alert.article.source} | {alert.article.link}",
                f"  {alert.rule.note}",
                "",
            ]

    if result.exit_reminders:
        lines.append("=== POSITIONS TO CONSIDER CLOSING ===")
        for reminder in result.exit_reminders:
            lines.append(f"- {reminder.note}")
        lines.append("")

    return "\n".join(lines)
