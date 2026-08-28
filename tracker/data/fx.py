"""GBP -> USD conversion.

The strategies here trade US-listed equities/ETFs (USD), but you fund the
account in GBP. `resolve_capital_usd` converts once per run using a live
GBPUSD rate from yfinance, falling back to `FX_FALLBACK_GBPUSD` (a static
rate you set in .env) if the network call fails — so a scheduled daily run
degrades gracefully instead of crashing on a transient FX-feed outage.
"""

from __future__ import annotations

import logging

from tracker.config import CACHE_DIR, settings

logger = logging.getLogger(__name__)

GBPUSD_TICKER = "GBPUSD=X"
_CACHE_FILE = CACHE_DIR / "fx_gbpusd.txt"


def fetch_gbpusd_rate(use_cache: bool = True) -> float:
    """Latest GBP/USD rate (1 GBP = N USD). Falls back to the last cached
    value, then to settings.fx_fallback_gbpusd, on any failure."""
    from datetime import datetime, timedelta

    from tracker.data.prices import _fetch_chart

    try:
        data = _fetch_chart(GBPUSD_TICKER, datetime.utcnow() - timedelta(days=5), datetime.utcnow())
        if data.empty:
            raise ValueError("empty GBPUSD history")
        rate = float(data["close"].dropna().iloc[-1])
        _CACHE_FILE.write_text(str(rate))
        return rate
    except Exception as exc:  # network/parsing errors of many possible types
        logger.warning("GBPUSD fetch failed (%s), falling back", exc)
        if use_cache and _CACHE_FILE.exists():
            try:
                return float(_CACHE_FILE.read_text().strip())
            except ValueError:
                pass
        return settings.fx_fallback_gbpusd


def gbp_to_usd(amount_gbp: float, rate: float | None = None) -> float:
    if rate is None:
        rate = fetch_gbpusd_rate()
    return amount_gbp * rate


def resolve_capital_usd(capital_gbp: float | None = None) -> tuple[float, float]:
    """Returns (capital_usd, rate_used) for the configured (or given) GBP
    starting capital."""
    capital_gbp = settings.initial_capital_gbp if capital_gbp is None else capital_gbp
    rate = fetch_gbpusd_rate()
    return capital_gbp * rate, rate
