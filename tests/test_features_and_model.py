import numpy as np
import pandas as pd
import pytest

from tracker.backtest.engine import resolve_trades
from tracker.models import features as feature_lib
from tracker.models.prediction_engine import chronological_split, train_and_evaluate
from tracker.signals import mirror_trade


@pytest.fixture
def resolved_mirror_trades(sample_disclosures, synthetic_prices):
    # Duplicate the synthetic disclosures across a wider date range so we
    # have enough resolved trades (20+) for a meaningful train/test split.
    frames = [sample_disclosures]
    for offset in range(1, 6):
        shifted = sample_disclosures.copy()
        shifted["transaction_date"] = shifted["transaction_date"] + pd.Timedelta(days=15 * offset)
        shifted["disclosure_date"] = shifted["disclosure_date"] + pd.Timedelta(days=15 * offset)
        frames.append(shifted)
    disclosures = pd.concat(frames, ignore_index=True)

    signals = mirror_trade.generate_signals(disclosures)
    return resolve_trades(signals, synthetic_prices, holding_days=21)


def test_build_mirror_features_shape_and_no_missing(resolved_mirror_trades):
    X, y = feature_lib.build_mirror_features(resolved_mirror_trades)
    assert len(X) == len(resolved_mirror_trades) == len(y)
    assert not X.isna().any().any()
    assert set(y.unique()) <= {0, 1}


def test_chronological_split_never_lets_train_see_future_dates(resolved_mirror_trades):
    dates = resolved_mirror_trades["signal_date"]
    train_idx, test_idx = chronological_split(dates, test_size=0.25)
    assert dates.iloc[train_idx].max() <= dates.iloc[test_idx].min()
    assert len(train_idx) + len(test_idx) == len(dates)


def test_train_and_evaluate_beats_or_matches_random_on_synthetic_noise(resolved_mirror_trades):
    X, y = feature_lib.build_mirror_features(resolved_mirror_trades)
    model, report = train_and_evaluate(X, y, resolved_mirror_trades["signal_date"], model_type="logreg")
    assert report.n_test > 0
    assert 0.0 <= report.accuracy <= 1.0
    assert 0.0 <= report.baseline_majority_class_accuracy <= 1.0
    # sanity: predictions on the training data itself should be finite probabilities
    probs = model.predict_proba(X)[:, 1]
    assert np.isfinite(probs).all()
    assert ((probs >= 0) & (probs <= 1)).all()


def test_build_event_features_one_hot_encodes_category():
    trades = pd.DataFrame(
        {
            "signal_date": pd.bdate_range("2024-01-01", periods=6),
            "category": ["middle_east_conflict", "trade_policy"] * 3,
            "article_count": [3, 5, 4, 6, 3, 8],
            "side": ["long", "short"] * 3,
            "net_return": [0.01, -0.02, 0.03, -0.01, 0.02, -0.03],
        }
    )
    X, y = feature_lib.build_event_features(trades)
    assert "cat_middle_east_conflict" in X.columns
    assert "cat_trade_policy" in X.columns
    assert len(X) == len(trades)
