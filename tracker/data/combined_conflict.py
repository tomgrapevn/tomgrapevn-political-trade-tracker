"""Merges tracker/data/trump_events.py and tracker/data/geopolitical_events.py
into one "any major state-conflict escalation" signal set, to test whether
the edge found in the Iran-only calendar is Trump/Iran-specific or a more
general market pattern. See README "Generalizing the escalation pattern".
"""

from __future__ import annotations

import pandas as pd

from tracker.data import geopolitical_events, trump_events


def combined_conflict_signals(include_deescalation: bool = False) -> pd.DataFrame:
    df = pd.concat([trump_events.to_signals_frame(), geopolitical_events.to_signals_frame()], ignore_index=True)
    is_conflict = df["category"].str.contains("conflict", case=False, na=False)
    is_deescalation = df["category"].str.endswith("deescalation")
    mask = is_conflict if include_deescalation else (is_conflict & ~is_deescalation)
    return df[mask].sort_values("signal_date").reset_index(drop=True)


def all_conflict_tickers() -> list[str]:
    return sorted(set(trump_events.all_tickers()) | set(geopolitical_events.all_tickers()))
