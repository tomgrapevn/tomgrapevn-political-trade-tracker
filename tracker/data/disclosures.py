"""Congressional trade disclosures (STOCK Act periodic transaction reports).

Data source: the "Senate Stock Watcher" / "House Stock Watcher" community
projects, which parse the raw PDF/paper filings members of Congress submit
under the STOCK Act into structured JSON, hosted for free on S3. No API key
needed. See README "What this can and can't see" for the disclosure-lag
caveat before treating these signals as timely.

    Senate: https://senatestockwatcher.com  (data: senate-stock-watcher-data.s3-us-west-2.amazonaws.com)
    House:  https://housestockwatcher.com   (data: house-stock-watcher-data.s3-us-west-2.amazonaws.com)

Both are unofficial, community-maintained parses of public filings — treat
them as best-effort, not a primary source. For anything load-bearing, cross
check against the official filings at https://efdsearch.senate.gov and
https://disclosures-clerk.house.gov.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import requests

from tracker.config import CACHE_DIR

logger = logging.getLogger(__name__)

SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
HOUSE_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"

_CACHE_FILE = CACHE_DIR / "disclosures.parquet"


def _normalize_senate(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df = df.rename(
        columns={
            "senator": "member",
            "ticker": "ticker",
            "transaction_date": "transaction_date",
            "type": "transaction_type",
            "amount": "amount_range",
            "asset_description": "asset_description",
            "owner": "owner",
        }
    )
    df["chamber"] = "senate"
    df["disclosure_date"] = pd.to_datetime(df.get("disclosure_date") or df.get("file_date"), errors="coerce")
    return df


def _normalize_house(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df = df.rename(
        columns={
            "representative": "member",
            "ticker": "ticker",
            "transaction_date": "transaction_date",
            "type": "transaction_type",
            "amount": "amount_range",
            "asset_description": "asset_description",
            "owner": "owner",
        }
    )
    df["chamber"] = "house"
    df["disclosure_date"] = pd.to_datetime(df.get("disclosure_date_raw") or df.get("disclosure_date"), errors="coerce")
    return df


_EXPECTED_COLUMNS = [
    "chamber",
    "member",
    "ticker",
    "transaction_type",
    "transaction_date",
    "disclosure_date",
    "amount_range",
    "owner",
    "asset_description",
]


def _fetch_json(url: str) -> list[dict]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_disclosures(use_cache: bool = True, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch and merge Senate + House disclosed-trade data.

    Falls back to the last cached parquet file if the network calls fail
    (e.g. running somewhere without open internet access) so downstream
    pipeline steps can still be exercised against real, if stale, data.
    """
    if use_cache and not force_refresh and _CACHE_FILE.exists():
        logger.info("Loading disclosures from cache: %s", _CACHE_FILE)
        return pd.read_parquet(_CACHE_FILE)

    frames = []
    for name, url, normalize in (
        ("senate", SENATE_URL, _normalize_senate),
        ("house", HOUSE_URL, _normalize_house),
    ):
        try:
            raw = _fetch_json(url)
            frames.append(normalize(raw))
            logger.info("Fetched %d %s disclosures", len(raw), name)
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to fetch %s disclosures (%s)", name, exc)
            if _CACHE_FILE.exists():
                logger.warning("Falling back to cached disclosures.")
                return pd.read_parquet(_CACHE_FILE)
            raise

    df = pd.concat(frames, ignore_index=True)
    for col in _EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[_EXPECTED_COLUMNS]

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[~df["ticker"].isin(["", "NAN", "--"])]
    df["transaction_type"] = df["transaction_type"].astype(str).str.lower().str.strip()
    df["disclosure_lag_days"] = (df["disclosure_date"] - df["transaction_date"]).dt.days

    df = df.dropna(subset=["transaction_date", "ticker"]).reset_index(drop=True)
    df.to_parquet(_CACHE_FILE)
    return df


def filter_watchlist(df: pd.DataFrame, watchlist: list[str]) -> pd.DataFrame:
    """Keep only rows whose `member` matches (case-insensitive substring) a
    name on `watchlist`. Empty watchlist = no filtering (everyone)."""
    if not watchlist:
        return df
    pattern = "|".join(pd.Series(watchlist).str.strip().str.lower().str.replace(r"([.^$*+?{}\[\]\\|()])", r"\\\1", regex=True))
    mask = df["member"].astype(str).str.lower().str.contains(pattern, na=False, regex=True)
    return df[mask].reset_index(drop=True)


def load_sample(path: str | Path) -> pd.DataFrame:
    """Load a locally saved disclosures file (parquet, json, or csv) — used
    by tests and by anyone running this without live internet access."""
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".json":
        return pd.DataFrame(json.loads(path.read_text()))
    return pd.read_csv(path, parse_dates=["transaction_date", "disclosure_date"])
