"""Policy/geopolitical keyword -> affected-ticker hypothesis map.

This is a *hypothesis*, not a fact: it encodes a plausible directional bet
(e.g. "Middle East conflict headlines tend to lift oil and defense names,
and pressure airlines on fuel-cost fears") for the event-driven signal to
test. `tracker.backtest` scores every entry here against 2 years of actual
price history — entries that don't hold up empirically should be trimmed or
re-weighted, not taken on faith. Edit this table to add/remove
keywords/tickers; nothing else needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventRule:
    keyword: str
    category: str
    tickers: tuple[str, ...]
    direction: str  # "long" or "short"
    rationale: str


EVENT_RULES: tuple[EventRule, ...] = (
    EventRule(
        keyword="Iran",
        category="middle_east_conflict",
        tickers=("XLE", "USO", "LMT", "RTX", "NOC", "GD"),
        direction="long",
        rationale="Middle East escalation headlines historically correlate with oil-price spikes and defense-sector strength.",
    ),
    EventRule(
        keyword="Strait of Hormuz",
        category="middle_east_conflict",
        tickers=("XLE", "USO"),
        direction="long",
        rationale="A key oil shipping chokepoint; disruption threats are priced into crude quickly.",
    ),
    EventRule(
        keyword="Iran",
        category="middle_east_conflict_airlines",
        tickers=("JETS", "DAL", "UAL", "AAL"),
        direction="short",
        rationale="Airlines are fuel-cost sensitive; oil spikes on Middle East conflict news tend to pressure the sector.",
    ),
    EventRule(
        keyword="tariff",
        category="trade_policy",
        tickers=("FXI", "EWZ", "SPY"),
        direction="short",
        rationale="Tariff announcements typically weigh on the targeted country's equities and broad risk sentiment.",
    ),
    EventRule(
        keyword="sanctions",
        category="trade_policy",
        tickers=("XLE", "GLD"),
        direction="long",
        rationale="Sanctions on energy-exporting states tend to tighten supply and lift oil/gold as a hedge.",
    ),
    EventRule(
        keyword="rate cut",
        category="monetary_policy",
        tickers=("XLK", "IWM"),
        direction="long",
        rationale="Rate cuts disproportionately help rate-sensitive growth and small-cap names.",
    ),
    EventRule(
        keyword="rate hike",
        category="monetary_policy",
        tickers=("XLK", "IWM"),
        direction="short",
        rationale="Rate hikes compress valuations most for rate-sensitive growth and small-cap names.",
    ),
    EventRule(
        keyword="executive order",
        category="executive_action",
        tickers=("SPY",),
        direction="long",
        rationale="Placeholder broad-market rule; replace with a ticker set specific to the order's sector once known.",
    ),
    EventRule(
        keyword="crypto",
        category="crypto_policy",
        tickers=("COIN", "BITO"),
        direction="long",
        rationale="Favorable crypto-policy headlines tend to lift crypto-exposed equities directly.",
    ),
    EventRule(
        keyword="immigration",
        category="labor_policy",
        tickers=("XLI",),
        direction="short",
        rationale="Placeholder — labor-supply-tightening headlines pressuring industrials with high manual-labor exposure.",
    ),
)


def rules_by_keyword() -> dict[str, list[EventRule]]:
    out: dict[str, list[EventRule]] = {}
    for rule in EVENT_RULES:
        out.setdefault(rule.keyword.lower(), []).append(rule)
    return out


def all_keywords() -> list[str]:
    return sorted({rule.keyword for rule in EVENT_RULES})


def all_tickers() -> list[str]:
    return sorted({t for rule in EVENT_RULES for t in rule.tickers})
