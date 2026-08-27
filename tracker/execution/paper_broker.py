"""Alpaca **paper-trading** execution stub.

This module places orders against Alpaca's paper-trading endpoint only —
fake money, real market data. It is not wired to any live/real-money
brokerage endpoint, and it never will be from this file: `_assert_paper_endpoint`
raises on anything that isn't `paper-api.alpaca.markets`, so there is no
config value that turns this into a live trader. If you eventually want to
trade with real money, that's a deliberate, separate decision you make in
your own brokerage account — not a flag flip here.

Get free paper-trading keys at https://alpaca.markets (no funding required,
it's a simulated account).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import pandas as pd
import requests

from tracker.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_HOST = "paper-api.alpaca.markets"


class LiveTradingBlockedError(RuntimeError):
    """Raised if ALPACA_BASE_URL doesn't point at the paper endpoint."""


def _assert_paper_endpoint(base_url: str) -> None:
    host = urlparse(base_url).hostname or ""
    if host != _ALLOWED_HOST:
        raise LiveTradingBlockedError(
            f"Refusing to trade against {base_url!r} — this module only trades "
            f"against https://{_ALLOWED_HOST} (paper/simulated money). "
            "Live execution is intentionally not implemented here."
        )


@dataclass(frozen=True)
class PaperBrokerClient:
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"

    def __post_init__(self):
        _assert_paper_endpoint(self.base_url)

    @property
    def _headers(self) -> dict:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def get_account(self) -> dict:
        resp = requests.get(f"{self.base_url}/v2/account", headers=self._headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def list_positions(self) -> list[dict]:
        resp = requests.get(f"{self.base_url}/v2/positions", headers=self._headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def submit_order(
        self, ticker: str, notional_usd: float, side: str, order_type: str = "market", time_in_force: str = "day"
    ) -> dict:
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        payload = {
            "symbol": ticker,
            "notional": round(notional_usd, 2),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        resp = requests.post(f"{self.base_url}/v2/orders", json=payload, headers=self._headers, timeout=15)
        resp.raise_for_status()
        return resp.json()


def client_from_settings() -> PaperBrokerClient:
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise RuntimeError("Set ALPACA_API_KEY and ALPACA_SECRET_KEY (paper keys) in .env first.")
    return PaperBrokerClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        base_url=settings.alpaca_base_url,
    )


def signals_to_orders(signals: pd.DataFrame, account_equity: float, max_position_pct: float) -> pd.DataFrame:
    """Turn the most recent signal per ticker into a proposed (not yet
    submitted) order sized as max_position_pct of current paper-account
    equity. Purely a sizing calculation — no network call."""
    if signals.empty:
        return pd.DataFrame(columns=["ticker", "side", "notional_usd"])

    latest = (
        signals.sort_values("signal_date")
        .groupby("ticker", as_index=False)
        .last()[["ticker", "side"]]
    )
    latest["order_side"] = latest["side"].map({"long": "buy", "short": "sell"})
    latest["notional_usd"] = round(max_position_pct * account_equity, 2)
    return latest[["ticker", "order_side", "notional_usd"]].rename(columns={"order_side": "side"})


def execute_orders(client: PaperBrokerClient, orders: pd.DataFrame, dry_run: bool = True) -> list[dict]:
    """Submit `orders` (as produced by signals_to_orders) to the paper
    account. dry_run=True (default) only logs what would be sent — pass
    dry_run=False explicitly to actually hit the paper API."""
    results = []
    for _, order in orders.iterrows():
        if dry_run:
            logger.info(
                "[DRY RUN] would submit paper order: %s %s $%.2f",
                order["side"],
                order["ticker"],
                order["notional_usd"],
            )
            results.append({**order.to_dict(), "status": "dry_run"})
            continue
        result = client.submit_order(order["ticker"], order["notional_usd"], order["side"])
        results.append(result)
    return results
