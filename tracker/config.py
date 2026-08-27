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

    initial_capital_usd: float = float(os.getenv("INITIAL_CAPITAL_USD", "500"))
    max_position_pct: float = float(os.getenv("MAX_POSITION_PCT", "0.10"))
    transaction_cost_bps: float = float(os.getenv("TRANSACTION_COST_BPS", "5"))

    alpaca_api_key: str | None = os.getenv("ALPACA_API_KEY") or None
    alpaca_secret_key: str | None = os.getenv("ALPACA_SECRET_KEY") or None
    alpaca_base_url: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    lookback_years: int = int(os.getenv("LOOKBACK_YEARS", "2"))


settings = Settings()
