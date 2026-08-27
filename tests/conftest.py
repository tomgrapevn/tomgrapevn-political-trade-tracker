"""Synthetic, fully offline fixtures.

This sandbox's outbound network is locked down to pypi/github, so these
tests exercise the real pipeline logic (feature engineering, backtest math,
model training) against hand-built/synthetic data instead of live fetches
from Senate/House Stock Watcher, yfinance, or GDELT. Anyone running this
repo with open internet access should also run it end-to-end against
`python -m tracker.cli fetch-data` — see README.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

TICKERS = ["AAPL", "XOM", "LMT", "SPY", "COIN"]
START = pd.Timestamp("2024-01-02")
END = pd.Timestamp("2026-01-02")


def _synthetic_price_series(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Deterministic geometric random walk, seeded off the ticker name so
    every test run (and every developer's machine) sees identical data."""
    dates = pd.bdate_range(start, end)
    seed = abs(hash(ticker)) % (2**32)
    rng = np.random.default_rng(seed)
    daily_returns = rng.normal(loc=0.0003, scale=0.015, size=len(dates))
    price = 100 * np.cumprod(1 + daily_returns)
    df = pd.DataFrame(
        {
            "open": price * 0.999,
            "high": price * 1.005,
            "low": price * 0.995,
            "close": price,
            "adj_close": price,
            "volume": rng.integers(1_000_000, 5_000_000, size=len(dates)),
        },
        index=dates,
    )
    df.index.name = "date"
    return df


@pytest.fixture(scope="session")
def synthetic_prices() -> dict[str, pd.DataFrame]:
    return {t: _synthetic_price_series(t, START, END) for t in TICKERS}


@pytest.fixture
def sample_disclosures() -> pd.DataFrame:
    """~20 synthetic Congressional trade disclosures spanning the 2-year
    window, with realistic STOCK Act disclosure lags (30-60 days)."""
    all_bdates = pd.bdate_range(START, END)
    transaction_dates = all_bdates[np.linspace(0, len(all_bdates) - 1, 20).astype(int)]
    rng = np.random.default_rng(42)
    rows = []
    members = ["Sen. Alpha Example", "Sen. Beta Sample", "Rep. Gamma Test"]
    for i, tx_date in enumerate(transaction_dates):
        lag_days = int(rng.integers(20, 60))
        rows.append(
            {
                "chamber": "senate" if i % 3 != 2 else "house",
                "member": members[i % len(members)],
                "ticker": TICKERS[i % len(TICKERS)],
                "transaction_type": "purchase" if i % 4 != 0 else "sale",
                "transaction_date": tx_date,
                "disclosure_date": tx_date + pd.Timedelta(days=lag_days),
                "amount_range": ["$1,001 - $15,000", "$15,001 - $50,000", "$50,001 - $100,000"][i % 3],
                "owner": "self",
                "asset_description": f"{TICKERS[i % len(TICKERS)]} common stock",
                "disclosure_lag_days": lag_days,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def sample_daily_events() -> pd.DataFrame:
    """Synthetic (date, keyword, article_count) rows matching keywords in
    tracker.data.event_map, spread across the window."""
    all_bdates = pd.bdate_range(START, END)
    dates = all_bdates[np.linspace(0, len(all_bdates) - 1, 15).astype(int)]
    keywords = ["Iran", "tariff", "rate cut", "sanctions"]
    rows = [
        {"date": d, "keyword": keywords[i % len(keywords)], "article_count": 3 + (i % 5)}
        for i, d in enumerate(dates)
    ]
    return pd.DataFrame(rows)
