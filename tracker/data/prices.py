"""Historical price data via yfinance (no API key required).

Caches per-ticker OHLCV to CACHE_DIR so repeated backtest runs don't re-hit
the network, and so this module still works (against stale data) somewhere
without open internet access.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from tracker.config import CACHE_DIR, settings

logger = logging.getLogger(__name__)

BENCHMARK_TICKER = "SPY"


def _cache_path(ticker: str) -> "Path":  # noqa: F821 - typing only
    from pathlib import Path

    safe = ticker.replace("/", "_")
    return CACHE_DIR / f"prices_{safe}.parquet"


def fetch_prices(
    tickers: list[str],
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    use_cache: bool = True,
) -> dict[str, pd.DataFrame]:
    """Fetch daily OHLCV for each ticker. Returns {ticker: DataFrame} with a
    DatetimeIndex and columns [open, high, low, close, adj_close, volume].
    """
    import yfinance as yf

    if start is None:
        start = datetime.utcnow() - timedelta(days=365 * settings.lookback_years)
    if end is None:
        end = datetime.utcnow()

    out: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        cache_file = _cache_path(ticker)
        if use_cache and cache_file.exists():
            df = pd.read_parquet(cache_file)
            if not df.empty and df.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=5):
                out[ticker] = df
                continue
        try:
            raw = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
            if raw.empty:
                logger.warning("No price data returned for %s", ticker)
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = [c[0] for c in raw.columns]
            raw = raw.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                }
            )
            raw.index.name = "date"
            raw.to_parquet(cache_file)
            out[ticker] = raw
        except Exception as exc:  # yfinance can raise a range of network/parse errors
            logger.warning("Failed to fetch prices for %s: %s", ticker, exc)
            if cache_file.exists():
                out[ticker] = pd.read_parquet(cache_file)

    return out


def fetch_benchmark(start=None, end=None, use_cache: bool = True) -> pd.DataFrame:
    return fetch_prices([BENCHMARK_TICKER], start=start, end=end, use_cache=use_cache).get(
        BENCHMARK_TICKER, pd.DataFrame()
    )


def forward_return(
    prices: pd.DataFrame, as_of: pd.Timestamp, horizon_days: int, price_col: str = "adj_close"
) -> float | None:
    """Return the close-to-close forward return over `horizon_days` trading
    days starting at (or after) `as_of`. None if there isn't enough data."""
    if prices.empty:
        return None
    idx = prices.index[prices.index >= as_of]
    if len(idx) == 0:
        return None
    start_pos = prices.index.get_loc(idx[0])
    end_pos = start_pos + horizon_days
    if end_pos >= len(prices):
        return None
    start_price = prices[price_col].iloc[start_pos]
    end_price = prices[price_col].iloc[end_pos]
    if start_price == 0 or pd.isna(start_price) or pd.isna(end_price):
        return None
    return float(end_price / start_price - 1.0)
