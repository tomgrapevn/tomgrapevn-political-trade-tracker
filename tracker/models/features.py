"""Feature engineering for the prediction engine.

Every feature here is computable strictly from information available *as of*
`signal_date` — no peeking at the outcome. That's the whole point of the
prediction engine: given what was knowable when the signal fired, was the
resulting trade more likely to work than not?
"""

from __future__ import annotations

import re

import pandas as pd

_AMOUNT_RANGE_RE = re.compile(r"\$?([\d,]+)\s*-\s*\$?([\d,]+)")


def _parse_amount_range(value: object) -> float:
    """STOCK Act filings report a dollar *range*, not an exact amount, e.g.
    "$1,001 - $15,000". Returns the midpoint, or NaN if unparseable."""
    if not isinstance(value, str):
        return float("nan")
    match = _AMOUNT_RANGE_RE.search(value.replace(",", ""))
    if not match:
        return float("nan")
    low, high = (int(g) for g in match.groups())
    return (low + high) / 2.0


def build_mirror_features(resolved_trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Features for the mirror-trade strategy. Target: did the (already
    cost-adjusted) trade return come out positive?"""
    df = resolved_trades.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])

    df["month"] = df["signal_date"].dt.month
    df["day_of_week"] = df["signal_date"].dt.dayofweek
    df["is_senate"] = (df.get("chamber") == "senate").astype(int)

    lag = pd.to_numeric(df.get("disclosure_lag_days"), errors="coerce")
    df["disclosure_lag_days"] = lag.fillna(lag.median() if lag.notna().any() else 0)

    amount_mid = df.get("amount_range", pd.Series(dtype=object)).map(_parse_amount_range)
    df["amount_mid_log"] = amount_mid.apply(lambda v: pd.NA if pd.isna(v) or v <= 0 else __import__("math").log10(v))
    df["amount_mid_log"] = pd.to_numeric(df["amount_mid_log"], errors="coerce").fillna(0)

    feature_cols = ["month", "day_of_week", "is_senate", "disclosure_lag_days", "amount_mid_log"]
    X = df[feature_cols].astype(float)
    y = (df["net_return"] > 0).astype(int)
    return X, y


def build_event_features(resolved_trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Features for the event-driven strategy. Target: did the trade
    return come out positive?"""
    df = resolved_trades.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])

    df["month"] = df["signal_date"].dt.month
    df["day_of_week"] = df["signal_date"].dt.dayofweek
    df["article_count"] = pd.to_numeric(df.get("article_count"), errors="coerce").fillna(0)
    df["side_is_long"] = (df.get("side") == "long").astype(int)

    category_dummies = pd.get_dummies(df.get("category", pd.Series(dtype=object)), prefix="cat")

    feature_cols = ["month", "day_of_week", "article_count", "side_is_long"]
    X = pd.concat([df[feature_cols].astype(float), category_dummies.astype(float)], axis=1)
    y = (df["net_return"] > 0).astype(int)
    return X, y
