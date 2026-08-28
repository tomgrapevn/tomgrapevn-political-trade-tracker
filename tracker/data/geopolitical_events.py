"""A second hand-verified event calendar, deliberately separate from
tracker/data/trump_events.py, covering non-Trump-attributed geopolitical
escalations: Russia-Ukraine and China-Taiwan tension. Same rationale as
trump_events.py (GDELT is down — see README), same standard: every row is
a specific, dated, independently-sourced event, not a vibe.

This exists to test whether "major state-conflict escalation -> long
defense (+ long oil for energy-relevant conflicts, short semiconductors
for Taiwan-specific tension) -> short airlines/exposed sectors" is a real,
general market pattern, or whether the edge found in trump_events.py's
Iran-focused calendar was specific to Trump/Iran. See
tracker.backtest.combined_conflict for how the two calendars merge for
that test, and README "Generalizing the escalation pattern" for the
result.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class GeopoliticalEvent:
    date: str
    category: str  # "conflict_escalation" or "conflict_deescalation"
    tickers: tuple[str, ...]
    direction: str
    description: str
    source: str


EVENT_CALENDAR: tuple[GeopoliticalEvent, ...] = (
    GeopoliticalEvent(
        "2024-05-23", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "China launches 'Joint Sword-2024A' large-scale military drills around Taiwan.",
        "Wikipedia 'Joint Sword-2024A'; The Diplomat",
    ),
    GeopoliticalEvent(
        "2024-05-23", "conflict_escalation", ("SOXX",), "short",
        "Same Joint Sword-2024A drills — semiconductor supply-chain risk (TSMC-adjacent).",
        "Wikipedia 'Joint Sword-2024A'",
    ),
    GeopoliticalEvent(
        "2024-08-06", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "Ukraine launches a surprise cross-border incursion into Russia's Kursk Oblast.",
        "Wikipedia 'August 2024 Kursk Oblast incursion'",
    ),
    GeopoliticalEvent(
        "2024-10-14", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "China launches 'Joint Sword-2024B' military drills around Taiwan.",
        "Wikipedia 'Joint Sword-2024B'; Army Recognition",
    ),
    GeopoliticalEvent(
        "2024-10-14", "conflict_escalation", ("SOXX",), "short",
        "Same Joint Sword-2024B drills.",
        "Wikipedia 'Joint Sword-2024B'",
    ),
    GeopoliticalEvent(
        "2025-04-01", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "China launches 'Strait Thunder-2025A' military drills near Matsu/Taiwan.",
        "Wikipedia 'Strait Thunder-2025A'; Jamestown Foundation",
    ),
    GeopoliticalEvent(
        "2025-04-01", "conflict_escalation", ("SOXX",), "short",
        "Same Strait Thunder-2025A drills.",
        "Wikipedia 'Strait Thunder-2025A'",
    ),
    GeopoliticalEvent(
        "2025-12-15", "conflict_deescalation", ("LMT", "RTX", "NOC", "GD"), "short",
        "Zelenskyy drops Ukraine's NATO membership bid at Berlin peace talks; European defense stocks slide on peace-deal hopes.",
        "CNBC 2025-12-15/16",
    ),
    GeopoliticalEvent(
        "2025-12-29", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "China launches 'Justice Mission-2025' military drills around Taiwan.",
        "Global Taiwan Institute",
    ),
    GeopoliticalEvent(
        "2025-12-29", "conflict_escalation", ("SOXX",), "short",
        "Same Justice Mission-2025 drills.",
        "Global Taiwan Institute",
    ),
)


def to_signals_frame() -> pd.DataFrame:
    rows = []
    for event in EVENT_CALENDAR:
        for ticker in event.tickers:
            rows.append(
                {
                    "signal_date": pd.Timestamp(event.date),
                    "ticker": ticker,
                    "side": event.direction,
                    "category": event.category,
                    "keyword": event.description,
                    "article_count": 1,
                    "rationale": f"{event.description} (source: {event.source})",
                }
            )
    return pd.DataFrame(rows).sort_values("signal_date").reset_index(drop=True)


def all_tickers() -> list[str]:
    return sorted({t for event in EVENT_CALENDAR for t in event.tickers})
