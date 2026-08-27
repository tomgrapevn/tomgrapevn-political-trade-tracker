"""Signal generator: mirror members of Congress's disclosed trades.

The realistic constraint this respects: you cannot act on a trade before it
is *disclosed*. STOCK Act periodic transaction reports are filed up to 45
days after the transaction date, and Senate Stock Watcher/House Stock
Watcher publish once the filing itself is processed — often later still. So
every signal here fires on `disclosure_date`, not `transaction_date`. See
README for how much of the historical "if I'd copied this trade" edge that
lag eats.
"""

from __future__ import annotations

import pandas as pd

_BUY_TYPES = {"purchase"}
_SELL_TYPES = {"sale", "sale (full)", "sale (partial)", "sale_full", "sale_partial"}


def generate_signals(disclosures: pd.DataFrame, include_shorts: bool = False) -> pd.DataFrame:
    """Turn a disclosures DataFrame (see tracker.data.disclosures) into a
    flat signal table: one row per (signal_date, ticker, member) with a
    `side` of "long" or "short".

    include_shorts=False (default) drops disclosed *sales* rather than
    treating them as short signals — a disclosed sale usually just means
    the filer trimmed/exited a position, which is weak evidence for
    shorting the stock, whereas a disclosed purchase is a direct, if
    lagged, buy signal worth testing.
    """
    df = disclosures.copy()
    df["transaction_type"] = df["transaction_type"].astype(str).str.lower().str.strip()

    df = df.dropna(subset=["disclosure_date", "ticker"])
    df = df[df["disclosure_date"].notna()]

    is_buy = df["transaction_type"].isin(_BUY_TYPES)
    is_sell = df["transaction_type"].isin(_SELL_TYPES)

    rows = []
    buys = df[is_buy].copy()
    buys["side"] = "long"
    rows.append(buys)

    if include_shorts:
        sells = df[is_sell].copy()
        sells["side"] = "short"
        rows.append(sells)

    if not rows or all(r.empty for r in rows):
        return pd.DataFrame(
            columns=["signal_date", "ticker", "side", "member", "chamber", "source_type", "disclosure_lag_days"]
        )

    out = pd.concat(rows, ignore_index=True)
    out = out.rename(columns={"disclosure_date": "signal_date"})
    out["source_type"] = "disclosure"
    return out[
        ["signal_date", "ticker", "side", "member", "chamber", "source_type", "disclosure_lag_days"]
    ].sort_values("signal_date").reset_index(drop=True)


def member_win_rates(signals_with_outcomes: pd.DataFrame) -> pd.DataFrame:
    """Given a signals frame that already has a `forward_return` column
    (see tracker.backtest.engine), aggregate hit rate and average return
    per member — useful for deciding which filers are actually worth
    following instead of the whole chamber."""
    df = signals_with_outcomes.dropna(subset=["forward_return"])
    if df.empty:
        return pd.DataFrame(columns=["member", "n_trades", "win_rate", "avg_forward_return"])
    grouped = df.groupby("member")["forward_return"]
    return (
        grouped.agg(
            n_trades="count",
            win_rate=lambda s: (s > 0).mean(),
            avg_forward_return="mean",
        )
        .reset_index()
        .sort_values("avg_forward_return", ascending=False)
    )
