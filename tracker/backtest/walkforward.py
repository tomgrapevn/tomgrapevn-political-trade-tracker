"""Walk-forward evaluation: the honest way to answer "would this have made
money over the last N months?"

A single backtest over one fixed historical window is easy to fool yourself
with — tune the holding period, the article-count threshold, or the model
hyperparameters until one combination looks great on that exact window, and
you've measured how well you can fit noise, not whether there's a real
edge. This module never lets the model train on a trade it couldn't have
known about yet: it rolls a training window forward one test block at a
time, predicts only on the next not-yet-seen block, and only "takes" the
trades the model scores above `prob_threshold` — then stitches every
out-of-sample test block into one continuous equity curve. That curve is
report-worthy in a way a single in-sample-tuned number is not.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tracker.models.prediction_engine import train_model


@dataclass
class FoldResult:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    n_train: int
    n_test_candidates: int
    n_test_taken: int


@dataclass
class WalkForwardResult:
    taken_trades: pd.DataFrame
    all_candidate_trades: pd.DataFrame
    folds: list[FoldResult]

    def fold_summary(self) -> pd.DataFrame:
        if not self.folds:
            return pd.DataFrame(
                columns=["train_start", "train_end", "test_start", "test_end", "n_train", "n_test_candidates", "n_test_taken"]
            )
        return pd.DataFrame([f.__dict__ for f in self.folds])


def _month_bounds(dates: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = dates.min().to_period("M").to_timestamp()
    end = (dates.max().to_period("M") + 1).to_timestamp()
    return start, end


def walk_forward_backtest(
    resolved_trades: pd.DataFrame,
    build_features_fn,
    train_months: int = 6,
    test_months: int = 1,
    model_type: str = "gbm",
    prob_threshold: float = 0.5,
    min_train_trades: int = 20,
) -> WalkForwardResult:
    """`resolved_trades` = output of tracker.backtest.engine.resolve_trades
    (needs signal_date, entry_date, exit_date, net_return + whatever raw
    columns `build_features_fn` reads). `build_features_fn` is
    tracker.models.features.build_mirror_features or build_event_features.

    A fold with fewer than `min_train_trades` training examples is skipped
    (its candidates are still recorded, with zero taken) rather than
    trained on too little data to mean anything.
    """
    trades = resolved_trades.sort_values("signal_date").reset_index(drop=True)
    if trades.empty:
        empty = trades.copy()
        return WalkForwardResult(taken_trades=empty, all_candidate_trades=empty, folds=[])

    start, end = _month_bounds(trades["signal_date"])
    taken_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    folds: list[FoldResult] = []

    cursor = start + pd.DateOffset(months=train_months)
    while cursor < end:
        train_start = cursor - pd.DateOffset(months=train_months)
        train_end = cursor
        test_start = cursor
        test_end = min(cursor + pd.DateOffset(months=test_months), end)

        train_df = trades[(trades["signal_date"] >= train_start) & (trades["signal_date"] < train_end)]
        test_df = trades[(trades["signal_date"] >= test_start) & (trades["signal_date"] < test_end)]
        candidate_frames.append(test_df)

        n_taken = 0
        if len(train_df) >= min_train_trades and not test_df.empty:
            X_train, y_train = build_features_fn(train_df)
            X_test, _ = build_features_fn(test_df)
            if y_train.nunique() > 1:
                model = train_model(X_train, y_train, model_type=model_type)
                proba = model.predict_proba(X_test)[:, 1]
                taken = test_df[proba >= prob_threshold]
                taken_frames.append(taken)
                n_taken = len(taken)

        folds.append(FoldResult(train_start, train_end, test_start, test_end, len(train_df), len(test_df), n_taken))
        cursor += pd.DateOffset(months=test_months)

    taken_trades = pd.concat(taken_frames, ignore_index=True) if taken_frames else trades.iloc[0:0].copy()
    all_candidates = pd.concat(candidate_frames, ignore_index=True) if candidate_frames else trades.iloc[0:0].copy()
    return WalkForwardResult(taken_trades=taken_trades, all_candidate_trades=all_candidates, folds=folds)
