"""Policy/geopolitical news search + keyword tagging.

Default provider is GDELT's DOC 2.0 API (https://api.gdeltproject.org),
which is free and requires no registration or API key — it indexes global
online news and supports full-text search with a date range. This module
only searches for and tags headlines against tracker.data.event_map's
keyword list; it does not do any sentiment/NLP beyond that keyword match by
default (see `tag_articles` to layer in something richer).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import requests

from tracker.config import CACHE_DIR
from tracker.data.event_map import all_keywords

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _cache_path(keyword: str) -> "object":
    from pathlib import Path

    safe = "".join(c if c.isalnum() else "_" for c in keyword.lower())
    return CACHE_DIR / f"news_{safe}.parquet"


def fetch_news_for_keyword(
    keyword: str,
    start: datetime,
    end: datetime,
    max_records: int = 250,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Search GDELT for articles matching `keyword` within [start, end]."""
    cache_file = _cache_path(keyword)
    if use_cache and cache_file.exists():
        return pd.read_parquet(cache_file)

    params = {
        "query": keyword,
        "mode": "artlist",
        "format": "json",
        "maxrecords": min(max_records, 250),
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }
    try:
        resp = requests.get(GDELT_DOC_API, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        articles = payload.get("articles", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("GDELT fetch failed for %r (%s)", keyword, exc)
        if cache_file.exists():
            return pd.read_parquet(cache_file)
        return pd.DataFrame(columns=["keyword", "title", "url", "published_at", "domain"])

    df = pd.DataFrame(articles)
    if df.empty:
        df = pd.DataFrame(columns=["keyword", "title", "url", "published_at", "domain"])
    else:
        df = df.rename(columns={"seendate": "published_at", "sourcecountry": "source_country"})
        df["keyword"] = keyword
        df["published_at"] = pd.to_datetime(df["published_at"], format="%Y%m%dT%H%M%SZ", errors="coerce")

    df.to_parquet(cache_file)
    return df


def fetch_policy_news(
    start: datetime | None = None,
    end: datetime | None = None,
    keywords: list[str] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Fetch and concatenate news for every keyword in the event map (or a
    custom `keywords` list). Each row is one article tagged with the
    keyword that surfaced it."""
    if start is None:
        start = datetime.utcnow() - timedelta(days=730)
    if end is None:
        end = datetime.utcnow()
    keywords = keywords or all_keywords()

    frames = [fetch_news_for_keyword(kw, start, end, use_cache=use_cache) for kw in keywords]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["keyword", "title", "url", "published_at", "domain"])
    return pd.concat(frames, ignore_index=True).dropna(subset=["published_at"])


def daily_event_dates(news_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse article-level rows to one row per (date, keyword) with an
    article count — the unit the event-driven signal actually trades on."""
    if news_df.empty:
        return pd.DataFrame(columns=["date", "keyword", "article_count"])
    df = news_df.copy()
    df["date"] = df["published_at"].dt.normalize()
    return (
        df.groupby(["date", "keyword"])
        .size()
        .reset_index(name="article_count")
        .sort_values("date")
        .reset_index(drop=True)
    )
