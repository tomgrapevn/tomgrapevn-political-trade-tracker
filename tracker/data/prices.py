"""Historical price data via Yahoo Finance's chart API (no API key needed).

Calls `query1.finance.yahoo.com/v8/finance/chart/<ticker>` directly with
`requests` rather than going through the `yfinance` package. Verified live
while building this: `yfinance`'s default session tries to fetch a
cookie/crumb from a *different* host (`fc.yahoo.com`) before every request,
and that specific handshake failed with SSL resets on this project's
network even though the chart endpoint itself worked fine — historical
daily bars don't need a crumb, so this skips that broken dependency
entirely. Yahoo's endpoints are also rate-limited per source IP (expect
occasional 429s, worse on a shared egress) — hence the retry/backoff below
and the inter-ticker delay in `fetch_prices`.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from tracker.config import CACHE_DIR, settings

logger = logging.getLogger(__name__)

BENCHMARK_TICKER = "SPY"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; political-trade-tracker research tool)"}


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("/", "_")
    return CACHE_DIR / f"prices_{safe}.parquet"


def _fetch_chart(
    ticker: str, start: datetime, end: datetime, interval: str = "1d", max_retries: int = 4
) -> pd.DataFrame:
    params = {"period1": int(start.timestamp()), "period2": int(end.timestamp()), "interval": interval}
    backoff = 2.0
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            resp = requests.get(
                CHART_URL.format(ticker=ticker), params=params, headers=_REQUEST_HEADERS, timeout=20
            )
            if resp.status_code == 429:
                logger.info("Rate limited fetching %s (attempt %d/%d), backing off %.0fs", ticker, attempt + 1, max_retries, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("chart", {}).get("result")
            if not results:
                logger.warning("No price data returned for %s", ticker)
                return pd.DataFrame()

            result = results[0]
            timestamps = result.get("timestamp", [])
            if not timestamps:
                return pd.DataFrame()
            quote = result["indicators"]["quote"][0]
            adjclose_block = result["indicators"].get("adjclose", [{}])[0]
            adjclose = adjclose_block.get("adjclose", quote.get("close"))

            df = pd.DataFrame(
                {
                    "open": quote.get("open"),
                    "high": quote.get("high"),
                    "low": quote.get("low"),
                    "close": quote.get("close"),
                    "adj_close": adjclose,
                    "volume": quote.get("volume"),
                },
                index=pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None).normalize(),
            )
            df.index.name = "date"
            return df.dropna(how="all")
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            last_exc = exc
            time.sleep(backoff)
            backoff *= 2

    logger.warning("Chart fetch failed for %s after %d attempts: %s", ticker, max_retries, last_exc)
    return pd.DataFrame()


def fetch_prices(
    tickers: list[str],
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    use_cache: bool = True,
    request_delay_seconds: float = 1.0,
) -> dict[str, pd.DataFrame]:
    """Fetch daily OHLCV for each ticker. Returns {ticker: DataFrame} with a
    DatetimeIndex and columns [open, high, low, close, adj_close, volume].
    """
    if start is None:
        start = datetime.utcnow() - timedelta(days=365 * settings.lookback_years)
    else:
        start = pd.Timestamp(start).to_pydatetime()
    if end is None:
        end = datetime.utcnow()
    else:
        end = pd.Timestamp(end).to_pydatetime()

    out: dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers):
        cache_file = _cache_path(ticker)
        if use_cache and cache_file.exists():
            df = pd.read_parquet(cache_file)
            if not df.empty and df.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=5):
                out[ticker] = df
                continue

        if i > 0:
            time.sleep(request_delay_seconds)  # spread requests out to avoid tripping Yahoo's rate limit

        raw = _fetch_chart(ticker, start, end)
        if raw.empty:
            if cache_file.exists():
                out[ticker] = pd.read_parquet(cache_file)
            continue
        raw.to_parquet(cache_file)
        out[ticker] = raw

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
