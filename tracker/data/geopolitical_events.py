"""A second hand-verified event calendar, deliberately separate from
tracker/data/trump_events.py, covering non-Trump-attributed geopolitical
escalations: Russia-Ukraine, China-Taiwan, Israel-Iran/Lebanon, and
India-Pakistan tension, plus one non-conflict resource-supply-risk event
(DRC/M23). Same rationale as trump_events.py (GDELT is down — see README),
same standard: every row is a specific, dated, independently-sourced
event, not a vibe.

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
    # --- Middle East beyond Iran-US (Israel-Lebanon/Hezbollah, Israel-Iran direct exchanges) ---
    GeopoliticalEvent(
        "2024-09-27", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "Israel kills Hezbollah leader Hassan Nasrallah in a Beirut airstrike, sharply escalating the Israel-Lebanon conflict.",
        "CNN 2024-09-27; CRS IF12770",
    ),
    GeopoliticalEvent(
        "2024-09-27", "conflict_escalation", ("XLE", "USO"), "long",
        "Same event — regional oil-supply-risk angle.",
        "CNN 2024-09-27",
    ),
    GeopoliticalEvent(
        "2024-10-01", "conflict_escalation", ("XLE", "USO", "LMT", "RTX", "NOC", "GD"), "long",
        "Iran launches ~200 ballistic missiles directly at Israel, the largest direct Iran-Israel exchange to that point.",
        "Wikipedia 'October 2024 Iranian strikes on Israel'; CNN",
    ),
    GeopoliticalEvent(
        "2024-10-26", "conflict_escalation", ("XLE", "USO", "LMT", "RTX", "NOC", "GD"), "long",
        "Israel retaliates with strikes on Iran ('Operation Days of Repentance') — note the strikes deliberately avoided Iranian oil infrastructure, which is itself a useful test of whether the blanket 'escalation -> long oil' rule holds even when supply isn't directly targeted.",
        "Wikipedia 'October 2024 Israeli strikes on Iran'; S&P Global Commodity Insights 2024-10-27",
    ),
    # --- South Asia: India-Pakistan ---
    GeopoliticalEvent(
        "2025-05-07", "conflict_escalation", ("LMT", "RTX", "NOC", "GD"), "long",
        "India launches 'Operation Sindoor' strikes on Pakistan after an April 2025 terror attack in Kashmir — the sharpest India-Pakistan military escalation in years. (India's own defense-manufacturer stocks, e.g. the Nifty Defence Index, rallied far harder than these global primes — not tested here since this project hasn't verified NSE-ticker data access; see README.)",
        "CNN 2025-05-07; Business Standard",
    ),
    # --- Sub-Saharan Africa: DRC / critical-minerals supply risk (a different mechanism, not conflict_escalation) ---
    GeopoliticalEvent(
        "2025-01-27", "resource_supply_risk", ("GLEN.L",), "long",
        "M23 rebels capture Goma, eastern DRC — a region controlling major cobalt/coltan supply; Glencore has DRC cobalt mining operations (an imperfect proxy: Glencore is a large diversified miner, not a pure DRC/cobalt play).",
        "Wikipedia '2025 Goma offensive'; AllAfrica 2025-01-27",
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
