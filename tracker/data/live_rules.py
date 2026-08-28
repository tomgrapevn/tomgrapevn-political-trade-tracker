"""Maps a live news match to the documented, backtested mechanical rule —
or to an explicit "detected but not validated" note when the matched
category is one this project actually tested and found *didn't* show a
reliable edge (de-escalation, tariffs, FOMC, crypto policy).

This is the deliberate alternative to letting an LLM improvise a reaction
to breaking news: every "validated" output here traces directly to a
result documented in README.md, reproducible by anyone re-running the
corresponding `backtest-*` command. Nothing here is a personalized
judgment call — it's the transparent output of a rule the user reviewed
and chose to automate.

Keyword matching against headlines is inherently imprecise — see
tracker/data/rss_monitor.py's docstring. A match here means "worth a
human look," not "confirmed."
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LiveRule:
    category: str
    keywords: tuple[str, ...]
    validated: bool
    tickers_long: tuple[str, ...] = ()
    tickers_short: tuple[str, ...] = ()
    holding_days: int = 10
    note: str = ""


# Every `validated=True` rule here corresponds to a category in the
# combined 15-date escalation finding (README "Generalizing the escalation
# pattern" / "Beyond the US"): 69% historical win rate, +2.0% average
# return per trade. `validated=False` rules correspond to hypotheses this
# project specifically tested and found didn't hold up — reported anyway
# so a real match doesn't go silently unmentioned, but explicitly labeled
# as not backed by a real edge.
LIVE_RULES: tuple[LiveRule, ...] = (
    LiveRule(
        category="middle_east_escalation",
        keywords=(
            "iran strikes", "strikes on iran", "israel strikes iran", "iran missile attack",
            "iran launches missile", "iranian nuclear site", "strait of hormuz blockade",
            "us strikes iran", "attack on israel", "hezbollah leader killed", "houthi strikes",
        ),
        validated=True,
        tickers_long=("XLE", "USO", "LMT", "RTX", "NOC", "GD"),
        tickers_short=("JETS",),
        holding_days=10,
        note="Middle East conflict escalation — 12 historical dates, 64% win rate, +2.4% avg return/trade.",
    ),
    LiveRule(
        category="ukraine_russia_escalation",
        keywords=("russian strikes on ukraine", "ukraine incursion", "kursk offensive", "kremlin strikes ukraine"),
        validated=True,
        tickers_long=("LMT", "RTX", "NOC", "GD"),
        holding_days=10,
        note="Russia-Ukraine conflict escalation — part of the 15-date combined escalation finding, 69% win rate.",
    ),
    LiveRule(
        category="taiwan_china_escalation",
        keywords=("taiwan strait drill", "china military drill near taiwan", "pla drill taiwan", "china conducts military exercises taiwan"),
        validated=True,
        tickers_long=("LMT", "RTX", "NOC", "GD"),
        tickers_short=("SOXX",),
        holding_days=10,
        note="China-Taiwan military escalation — part of the 15-date combined escalation finding, 69% win rate.",
    ),
    LiveRule(
        category="india_pakistan_escalation",
        keywords=("india strikes pakistan", "pakistan strikes india", "india pakistan military strikes", "kashmir attack escalation"),
        validated=True,
        tickers_long=("LMT", "RTX", "NOC", "GD"),
        holding_days=10,
        note="India-Pakistan military escalation — part of the 15-date combined escalation finding, 69% win rate.",
    ),
    LiveRule(
        category="conflict_deescalation",
        keywords=("ceasefire agreed", "peace deal reached", "peace talks progress", "truce agreed"),
        validated=False,
        note="De-escalation/ceasefire news detected — tested and found NOT reliable (38-42% win rate across all three conflict calendars). Informational only; the documented rule does not suggest a trade here.",
    ),
    LiveRule(
        category="tariff_policy",
        keywords=("new tariffs announced", "tariff increase", "trade war escalates"),
        validated=False,
        note="Tariff policy news detected — tested and found weak/inconsistent (38% win rate). Informational only.",
    ),
    LiveRule(
        category="monetary_policy",
        keywords=("federal reserve rate decision", "fomc decision", "fed chair"),
        validated=False,
        note="Fed/monetary policy news detected — the pre-FOMC drift hypothesis was tested and failed (47.6% win rate, worse than a coin flip). Informational only.",
    ),
    LiveRule(
        category="crypto_policy",
        keywords=("crypto executive order", "digital asset regulation", "strategic bitcoin reserve"),
        validated=False,
        note="Crypto policy news detected — the one historical test of this lost badly (-15.4% avg). Informational only.",
    ),
)


def match_rules(text: str) -> list[LiveRule]:
    text_lower = text.lower()
    return [rule for rule in LIVE_RULES if any(kw in text_lower for kw in rule.keywords)]
