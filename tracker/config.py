"""Central configuration loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
REPORTS_DIR = ROOT_DIR / "reports"

for _dir in (DATA_DIR, CACHE_DIR, REPORTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _list_env(name: str) -> list[str]:
    val = os.getenv(name, "")
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    watchlist: list[str] = field(default_factory=lambda: _list_env("WATCHLIST"))

    price_data_provider: str = os.getenv("PRICE_DATA_PROVIDER", "yfinance")

    newsapi_key: str | None = os.getenv("NEWSAPI_KEY") or None

    # Base currency for sizing is GBP (what you'd actually be funding the
    # account with); tracker/data/fx.py converts to USD at run time since
    # the underlying instruments (US-listed equities/ETFs) trade in USD.
    initial_capital_gbp: float = float(os.getenv("INITIAL_CAPITAL_GBP", "500"))
    fx_fallback_gbpusd: float = float(os.getenv("FX_FALLBACK_GBPUSD", "1.27"))
    max_position_pct: float = float(os.getenv("MAX_POSITION_PCT", "0.10"))
    transaction_cost_bps: float = float(os.getenv("TRANSACTION_COST_BPS", "5"))

    alpaca_api_key: str | None = os.getenv("ALPACA_API_KEY") or None
    alpaca_secret_key: str | None = os.getenv("ALPACA_SECRET_KEY") or None
    alpaca_base_url: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    lookback_years: int = int(os.getenv("LOOKBACK_YEARS", "2"))

    # Wealthy/notable individuals to track via SEC Form 4 insider filings
    # (see tracker/data/insider_trades.py) — distinct from WATCHLIST, which
    # is matched against Congressional STOCK Act disclosures.
    watched_insiders: list[str] = field(
        default_factory=lambda: _list_env("WATCHED_INSIDERS") or ["Elon Musk", "Jeff Bezos"]
    )
    sec_edgar_contact: str = os.getenv("SEC_EDGAR_CONTACT", "research-contact@example.com")

    # Local daily run time, informational only — actual scheduling is done
    # by whatever cron/trigger invokes `python -m tracker.cli daily-run`.
    daily_run_time_uk: str = os.getenv("DAILY_RUN_TIME_UK", "07:00")

    # What "beating the market" is measured against. Default is a proxy,
    # not an exact match: BlackRock's "iShares World Equity Index Fund"
    # (e.g. as offered through Wise Assets UK) tracks the MSCI World Index
    # but is a Luxembourg-domiciled OEIC with no exchange ticker to pull
    # live prices from. SWDA.L (iShares Core MSCI World UCITS ETF, GBP,
    # same provider, same underlying index) is the closest fetchable
    # stand-in — expect returns to track closely but not identically
    # (different share class, minor fee/tracking-error differences).
    benchmark_ticker: str = os.getenv("BENCHMARK_TICKER", "SWDA.L")


settings = Settings()
