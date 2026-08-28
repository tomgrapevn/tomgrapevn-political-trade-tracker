"""Live news monitoring via free, no-key RSS feeds.

This exists because GDELT (the general-purpose live news API this project
tried first) has a broken TLS certificate on the provider's end, and paid
news APIs aren't needed: verified live while building this, these wire/
official RSS feeds are free, require no signup or key, and are exactly the
kind of source that carries a major escalation headline within minutes.

    BBC World News, Al Jazeera, UN News, and the US Department of War's
    (formerly Department of Defense) own newsroom feed.

**Be honest about what this is and isn't.** Every event in
tracker/data/trump_events.py and geopolitical_events.py was found by a
human (well, an AI doing the same job a human researcher would) manually
reading multiple sources, cross-checking dates, and confirming the market
reaction — that's what made the backtest results trustworthy. This module
does none of that: it's a keyword match against RSS headlines, run
unattended. It WILL produce false positives (a headline mentioning "Iran"
in a context that isn't a military escalation) and WILL miss things a
human would catch. Treat its output as "worth a human look," not as
verified events on the same footing as the hand-checked calendars.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from tracker.config import CACHE_DIR

logger = logging.getLogger(__name__)

FEEDS: dict[str, str] = {
    "bbc_world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "al_jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "un_news": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    "defense_gov": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945",
}

_STATE_FILE = CACHE_DIR / "rss_monitor_state.json"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; political-trade-tracker news monitor)"}


@dataclass(frozen=True)
class Article:
    source: str
    title: str
    link: str
    description: str
    published: datetime | None


def _parse_rss(xml_bytes: bytes, source: str) -> list[Article]:
    articles = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("Failed to parse RSS from %s: %s", source, exc)
        return articles

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date_raw = item.findtext("pubDate")
        published = None
        if pub_date_raw:
            try:
                published = parsedate_to_datetime(pub_date_raw)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published = None
        if title and link:
            articles.append(Article(source=source, title=title, link=link, description=description, published=published))
    return articles


def fetch_all_feeds(timeout: int = 20) -> list[Article]:
    all_articles: list[Article] = []
    for name, url in FEEDS.items():
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            all_articles.extend(_parse_rss(resp.content, name))
        except requests.RequestException as exc:
            logger.warning("Failed to fetch feed %s (%s): %s", name, url, exc)
    return all_articles


def load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"seen_links": [], "open_signals": []}


def save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def filter_new_articles(articles: list[Article], state: dict, max_seen: int = 5000) -> list[Article]:
    seen = set(state.get("seen_links", []))
    new = [a for a in articles if a.link not in seen]
    updated_seen = list(seen | {a.link for a in new})
    state["seen_links"] = updated_seen[-max_seen:]
    return new
