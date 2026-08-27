import math

from tracker.config import settings
from tracker.data.fx import fetch_gbpusd_rate, gbp_to_usd, resolve_capital_usd


def test_gbp_to_usd_with_explicit_rate_is_pure_arithmetic():
    assert math.isclose(gbp_to_usd(500, rate=1.30), 650.0)


def test_fetch_gbpusd_rate_returns_a_sane_positive_float():
    # This sandbox's outbound network is restricted, so this exercises the
    # real fallback path (see fx.py) rather than a live fetch — either way
    # the contract is "always returns something usable, never raises".
    rate = fetch_gbpusd_rate()
    assert rate > 0
    assert rate < 10  # sanity bound; GBPUSD has never been anywhere near this


def test_resolve_capital_usd_uses_configured_gbp_amount():
    capital_usd, rate = resolve_capital_usd(capital_gbp=500.0)
    assert math.isclose(capital_usd, 500.0 * rate)


def test_resolve_capital_usd_defaults_to_settings_initial_capital_gbp():
    capital_usd, rate = resolve_capital_usd()
    assert math.isclose(capital_usd, settings.initial_capital_gbp * rate)
