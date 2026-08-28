"""A hand-verified calendar of Trump administration policy/geopolitical
announcements, for backtesting the "react to his announcements" strategy
without depending on a live news feed.

This exists because `tracker/data/news.py` (GDELT) is currently unusable —
its TLS certificate is broken server-side (see README "Live-data status").
Rather than fake a live feed, every row below is a specific, dated,
independently-sourced event: verified via web search while building this
(sources noted per entry) — announcement dates, not vibes. This is not a
substitute for a live feed going forward (it will not pick up *new*
announcements on its own — see README for how to extend it), but it is a
real, checkable dataset for "would reacting to his last ~18 months of major
announcements have made money."

Direction/ticker choices are hypotheses consistent with tracker/data/event_map.py's
approach (e.g. tariff escalation -> short the targeted country/sector;
Middle East military escalation -> long oil/defense, short airlines) —
`tracker/backtest/engine.py` is what actually tests whether each held up,
not this file.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TrumpEvent:
    date: str  # ISO date, the announcement/effective date used as signal_date
    category: str
    tickers: tuple[str, ...]
    direction: str  # "long" or "short"
    description: str
    source: str


EVENT_CALENDAR: tuple[TrumpEvent, ...] = (
    TrumpEvent(
        "2025-02-01", "tariff_policy", ("EWC", "SPY"), "short",
        "25% tariff on most Canadian goods, 10% on Canadian energy, announced.",
        "PBS News tariff timeline",
    ),
    TrumpEvent(
        "2025-04-02", "tariff_policy", ("SPY", "XRT", "FXI"), "short",
        "'Liberation Day': universal 10% tariff + steep country-specific reciprocal tariffs announced.",
        "Congress.gov CRS R48549; Wikipedia 'Liberation Day tariffs'",
    ),
    TrumpEvent(
        "2025-04-09", "tariff_policy_reversal", ("SPY", "XRT"), "long",
        "90-day tariff pause announced for multiple countries (China excluded).",
        "PBS News tariff timeline",
    ),
    TrumpEvent(
        "2025-04-09", "tariff_policy", ("FXI",), "short",
        "China tariffs raised to 145% effective, even as other countries got a pause.",
        "China Briefing; Euronews",
    ),
    TrumpEvent(
        "2025-03-15", "middle_east_conflict", ("XLE", "USO"), "long",
        "Trump orders 'decisive' US strikes on Iran-aligned Houthis in Yemen after Red Sea shipping attacks resume.",
        "CNN 2025-03-15; ABC News",
    ),
    TrumpEvent(
        "2025-03-15", "middle_east_conflict", ("JETS",), "short",
        "Same Houthi-strikes event — Red Sea shipping/oil-cost shock.",
        "CNN 2025-03-15",
    ),
    TrumpEvent(
        "2025-05-06", "middle_east_conflict_deescalation", ("XLE", "USO"), "short",
        "Trump declares ceasefire with the Houthis (Oman-mediated), strikes stop 'effective immediately'.",
        "Wikipedia '2025 United States-Houthi ceasefire'; FDD",
    ),
    TrumpEvent(
        "2025-05-06", "middle_east_conflict_deescalation", ("JETS",), "long",
        "Same Houthi-ceasefire event.",
        "Wikipedia '2025 United States-Houthi ceasefire'",
    ),
    TrumpEvent(
        "2025-06-22", "middle_east_conflict", ("XLE", "USO", "LMT", "RTX", "NOC", "GD"), "long",
        "US strikes on Iranian nuclear sites (Fordow, Natanz, Isfahan) — start of the '12 Day War'.",
        "Wikipedia '2025 United States strikes on Iranian nuclear sites'",
    ),
    TrumpEvent(
        "2025-06-22", "middle_east_conflict", ("JETS",), "short",
        "Same event as above — airlines sensitive to an oil-price/conflict shock.",
        "Wikipedia '2025 United States strikes on Iranian nuclear sites'",
    ),
    TrumpEvent(
        "2025-06-24", "middle_east_conflict_deescalation", ("XLE", "USO"), "short",
        "Trump announces Israel-Iran ceasefire, ending the '12 Day War'.",
        "Wikipedia '2025 United States strikes on Iranian nuclear sites'",
    ),
    TrumpEvent(
        "2025-06-24", "middle_east_conflict_deescalation", ("JETS",), "long",
        "Same ceasefire — relief for fuel-cost-sensitive airlines.",
        "Wikipedia '2025 United States strikes on Iranian nuclear sites'",
    ),
    TrumpEvent(
        "2025-08-06", "tariff_policy", ("INDA",), "short",
        "Executive order imposing additional 25% tariff on India over Russian oil purchases (-> 50% cumulative).",
        "Bloomberg; CNBC 2025-08-06",
    ),
    TrumpEvent(
        "2026-01-14", "tariff_policy", ("SOXX",), "short",
        "Proclamations adjusting tariffs on semiconductor imports and processed critical minerals.",
        "Ballotpedia trade/tariff executive actions 2025-2026",
    ),
    TrumpEvent(
        "2026-01-30", "monetary_policy", ("XLK", "IWM"), "short",
        "Trump nominates Kevin Warsh (characterized as an inflation hawk) to succeed Powell as Fed chair.",
        "CNN; NBC News 2026-01-30",
    ),
    TrumpEvent(
        "2026-02-06", "middle_east_conflict", ("XLE",), "long",
        "Executive orders imposing further tariffs/sanctions related to Iran and Russia.",
        "Ballotpedia trade/tariff executive actions 2025-2026",
    ),
    TrumpEvent(
        "2026-02-28", "middle_east_conflict", ("XLE", "USO", "LMT", "RTX", "NOC", "GD"), "long",
        "'Major combat operations' against Iran announced — joint US-Israel strikes begin the 2026 Iran war.",
        "Wikipedia '2026 Iran war'; '2026 United States military buildup in the Middle East'",
    ),
    TrumpEvent(
        "2026-02-28", "middle_east_conflict", ("JETS",), "short",
        "Same event as above.",
        "Wikipedia '2026 Iran war'",
    ),
    TrumpEvent(
        "2026-04-08", "middle_east_conflict_deescalation", ("XLE", "USO"), "short",
        "Ceasefire takes effect after 40 days of the 2026 Iran war.",
        "Wikipedia '2026 Iran war'",
    ),
    TrumpEvent(
        "2026-04-13", "middle_east_conflict", ("XLE", "USO"), "long",
        "US naval blockade of Iran imposed after ceasefire talks failed.",
        "Wikipedia '2026 United States naval blockade of Iran'",
    ),
    TrumpEvent(
        "2026-07-08", "middle_east_conflict", ("XLE", "USO", "LMT", "RTX", "NOC", "GD"), "long",
        "The April ceasefire collapses; Trump declares the deal 'over' and the US resumes major strikes on Iran (Iranshahr, Bandar Abbas, Konarak, Chabahar, Bushehr, Aq Qala) — found via the live RSS monitor (Dept. of War newsroom feed), verified against an independent source before adding.",
        "Al Jazeera 2026-07-08; Dept. of War newsroom (multiple dated releases, e.g. 'U.S. Concludes 13th Night of Strikes on Iranian Military Targets', 2026-07-24)",
    ),
    TrumpEvent(
        "2026-07-08", "middle_east_conflict", ("JETS",), "short",
        "Same event as above.",
        "Al Jazeera 2026-07-08",
    ),
    TrumpEvent(
        "2026-05-19", "crypto_policy", ("COIN", "BITO"), "long",
        "Executive order integrating crypto/fintech into the traditional financial system; Fed to assess crypto master-account access.",
        "White House fact sheet 2026-05-19; Bitcoin Magazine",
    ),
    TrumpEvent(
        "2026-05-22", "monetary_policy", ("XLK", "IWM"), "short",
        "Kevin Warsh takes office as Fed chair, succeeding Powell.",
        "Brookings Fed roster tracker",
    ),
    TrumpEvent(
        "2026-08-14", "middle_east_conflict", ("XLE", "USO"), "long",
        "Trump says he will designate the Strait of Hormuz a US territory 'pretty soon' amid ongoing blockade standoff.",
        "Al Jazeera 2026-08-16",
    ),
    TrumpEvent(
        "2026-08-19", "middle_east_conflict", ("XLE", "USO"), "long",
        "Trump announces 'Economic D-Day' against Iran — sanctions threat on any country/institution aiding Iran, after nuclear talks collapsed. Note: reported to have unsettled broader US markets too (Al Jazeera 2026-08-21), not a clean one-directional event — included for completeness even though the simple long-oil hypothesis may not hold here.",
        "CNBC 2026-08-19; NPR 2026-08-21",
    ),
)


def to_signals_frame() -> pd.DataFrame:
    """Expand the calendar into the same signal schema
    tracker.signals.event_driven.generate_signals produces, so it plugs
    directly into tracker.backtest.engine.resolve_trades /
    tracker.models.features.build_event_features unchanged."""
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
