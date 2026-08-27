import numpy as np
import pandas as pd
import pytest

from tracker.backtest.walkforward import walk_forward_backtest
from tracker.models.features import build_mirror_features


@pytest.fixture
def long_history_trades() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="2D")
    return pd.DataFrame(
        {
            "signal_date": dates,
            "chamber": rng.choice(["senate", "house"], size=n),
            "disclosure_lag_days": rng.integers(20, 60, size=n),
            "amount_range": rng.choice(["$1,001 - $15,000", "$15,001 - $50,000"], size=n),
            "net_return": rng.normal(0, 0.05, size=n),
        }
    )


def test_folds_never_test_on_dates_the_training_window_could_see(long_history_trades):
    result = walk_forward_backtest(long_history_trades, build_mirror_features, train_months=6, test_months=1, min_train_trades=5)
    assert len(result.folds) > 0
    for fold in result.folds:
        assert fold.train_start < fold.train_end == fold.test_start
        assert fold.test_start <= fold.test_end


def test_folds_roll_forward_without_gaps_or_overlap(long_history_trades):
    result = walk_forward_backtest(long_history_trades, build_mirror_features, train_months=6, test_months=1, min_train_trades=5)
    for a, b in zip(result.folds, result.folds[1:]):
        assert b.test_start == a.test_end


def test_taken_trades_are_a_subset_of_candidate_trades_by_signal_date(long_history_trades):
    result = walk_forward_backtest(long_history_trades, build_mirror_features, train_months=6, test_months=1, min_train_trades=5)
    if not result.taken_trades.empty:
        assert set(result.taken_trades["signal_date"]) <= set(result.all_candidate_trades["signal_date"])
        assert len(result.taken_trades) <= len(result.all_candidate_trades)


def test_fold_summary_matches_folds_list(long_history_trades):
    result = walk_forward_backtest(long_history_trades, build_mirror_features, train_months=6, test_months=1, min_train_trades=5)
    summary = result.fold_summary()
    assert len(summary) == len(result.folds)
    assert (summary["n_test_taken"] <= summary["n_test_candidates"]).all()


def test_insufficient_history_yields_no_folds_and_empty_result():
    tiny = pd.DataFrame(
        {
            "signal_date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "chamber": ["senate"] * 3,
            "disclosure_lag_days": [30, 40, 50],
            "amount_range": ["$1,001 - $15,000"] * 3,
            "net_return": [0.01, -0.01, 0.02],
        }
    )
    result = walk_forward_backtest(tiny, build_mirror_features, train_months=6, test_months=1)
    assert result.folds == []
    assert result.taken_trades.empty


def test_empty_input_returns_empty_result_not_an_error():
    empty = pd.DataFrame(columns=["signal_date", "chamber", "disclosure_lag_days", "amount_range", "net_return"])
    result = walk_forward_backtest(empty, build_mirror_features)
    assert result.taken_trades.empty
    assert result.folds == []
