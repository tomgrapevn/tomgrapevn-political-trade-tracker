"""Scheduled macroeconomic announcement dates — a higher-frequency,
non-crisis alternative to the conflict-escalation calendars.

Unlike Iran/Ukraine/Taiwan (rare, unscheduled crises), FOMC meeting dates
are published by the Federal Reserve years in advance and recur 8 times a
year on a fixed public calendar — guaranteed to continue for as long as the
Fed exists, which is a much safer "will this still be happening in 24
months" bet than any specific war.

The hypothesis tested here is not "guess which way the Fed surprises
markets" (this calendar doesn't attempt that, and doing it honestly would
need real-time consensus-forecast data this project doesn't have). It's
the **pre-FOMC announcement drift**: a specific, published finding that
average stock returns are abnormally elevated in the ~24 hours before
scheduled FOMC announcements, regardless of the decision itself —
compensation for holding through resolvable macro-policy uncertainty, not
a bet on the outcome.

    Lucca, D. and E. Moench (2015), "The Pre-FOMC Announcement Drift,"
    The Journal of Finance, 70(1), 329-371.

Meeting dates are the Federal Reserve's own published schedule
(https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) —
`meeting_start` is the signal date (position opens at that day's close),
`decision_date` is the announcement day (~24 hours later, `holding_days=1`
in the CLI trades from the close before to the close after).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# (meeting_start, decision_date) — the Fed's own two-day meeting calendar.
# 2026 dates from the September 2025-confirmed schedule; the Fed notes
# each is "tentative until confirmed at the meeting immediately preceding
# it," so treat late-2026 dates as provisional.
FOMC_MEETINGS: tuple[tuple[str, str], ...] = (
    ("2024-01-30", "2024-01-31"),
    ("2024-03-19", "2024-03-20"),
    ("2024-04-30", "2024-05-01"),
    ("2024-06-11", "2024-06-12"),
    ("2024-07-30", "2024-07-31"),
    ("2024-09-17", "2024-09-18"),
    ("2024-11-06", "2024-11-07"),
    ("2024-12-10", "2024-12-11"),
    ("2025-01-28", "2025-01-29"),
    ("2025-03-18", "2025-03-19"),
    ("2025-05-06", "2025-05-07"),
    ("2025-06-17", "2025-06-18"),
    ("2025-07-29", "2025-07-30"),
    ("2025-09-16", "2025-09-17"),
    ("2025-10-28", "2025-10-29"),
    ("2025-12-09", "2025-12-10"),
    ("2026-01-27", "2026-01-28"),
    ("2026-03-17", "2026-03-18"),
    ("2026-04-28", "2026-04-29"),
    ("2026-06-16", "2026-06-17"),
    ("2026-07-28", "2026-07-29"),
    ("2026-09-15", "2026-09-16"),
    ("2026-10-27", "2026-10-28"),
    ("2026-12-08", "2026-12-09"),
)

PRE_FOMC_TICKER = "SPY"  # the Lucca-Moench finding is specifically a US-equity effect
SOURCE = "Federal Reserve FOMC meeting calendar; Lucca & Moench (2015) 'The Pre-FOMC Announcement Drift', Journal of Finance"


@dataclass(frozen=True)
class MacroEvent:
    signal_date: str
    ticker: str
    side: str
    category: str
    description: str
    source: str


def to_signals_frame() -> pd.DataFrame:
    rows = [
        {
            "signal_date": pd.Timestamp(meeting_start),
            "ticker": PRE_FOMC_TICKER,
            "side": "long",
            "category": "fomc_pre_drift",
            "keyword": f"Pre-FOMC drift ahead of the {decision_date} rate decision",
            "article_count": 1,
            "rationale": f"Scheduled FOMC decision on {decision_date}; long through the announcement per the documented pre-FOMC drift. (source: {SOURCE})",
        }
        for meeting_start, decision_date in FOMC_MEETINGS
    ]
    return pd.DataFrame(rows).sort_values("signal_date").reset_index(drop=True)


def all_tickers() -> list[str]:
    return [PRE_FOMC_TICKER]
