"""A deliberately simple prediction engine, trained and evaluated with a
chronological (not random) train/test split — shuffling would leak future
information into training, which is the single most common way backtests
lie to you.

The bar for "this model is worth anything" is the baseline: does it beat
(a) always predicting the majority class and (b) an unconditional coin
flip, out of sample? If it doesn't clear both by a real margin, treat the
signal as noise, not edge — see README.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_REGISTRY = {
    "logreg": lambda: LogisticRegression(max_iter=1000),
    "gbm": lambda: GradientBoostingClassifier(random_state=0),
}


def chronological_split(
    dates: pd.Series, test_size: float = 0.2
) -> tuple[np.ndarray, np.ndarray]:
    """Split row indices by time: the earliest (1 - test_size) fraction of
    dates trains, the most recent test_size fraction tests. Returns
    (train_idx, test_idx) as positional integer arrays."""
    order = np.argsort(dates.values)
    cutoff = int(len(order) * (1 - test_size))
    return order[:cutoff], order[cutoff:]


def train_model(
    X: pd.DataFrame, y: pd.Series, model_type: str = "gbm"
) -> Pipeline:
    if model_type not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model_type {model_type!r}; choose one of {list(MODEL_REGISTRY)}")
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", MODEL_REGISTRY[model_type]()),
        ]
    )
    pipeline.fit(X, y)
    return pipeline


@dataclass(frozen=True)
class EvaluationReport:
    n_test: int
    accuracy: float
    precision: float
    recall: float
    roc_auc: float | None
    baseline_majority_class_accuracy: float

    def to_dict(self) -> dict:
        return {
            "n_test": self.n_test,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "roc_auc": self.roc_auc,
            "baseline_majority_class_accuracy": self.baseline_majority_class_accuracy,
            "beats_baseline": (self.accuracy - self.baseline_majority_class_accuracy) if self.roc_auc is not None else None,
        }


def evaluate_model(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> EvaluationReport:
    if len(X_test) == 0:
        raise ValueError("Empty test set — need more resolved trades before evaluating.")

    y_pred = model.predict(X_test)
    majority_class = y_test.mode().iloc[0]
    baseline_acc = float((y_test == majority_class).mean())

    roc_auc = None
    if y_test.nunique() > 1:
        try:
            y_proba = model.predict_proba(X_test)[:, 1]
            roc_auc = float(roc_auc_score(y_test, y_proba))
        except (AttributeError, ValueError):
            roc_auc = None

    return EvaluationReport(
        n_test=len(X_test),
        accuracy=float(accuracy_score(y_test, y_pred)),
        precision=float(precision_score(y_test, y_pred, zero_division=0)),
        recall=float(recall_score(y_test, y_pred, zero_division=0)),
        roc_auc=roc_auc,
        baseline_majority_class_accuracy=baseline_acc,
    )


def train_and_evaluate(
    X: pd.DataFrame, y: pd.Series, dates: pd.Series, model_type: str = "gbm", test_size: float = 0.2
) -> tuple[Pipeline, EvaluationReport]:
    train_idx, test_idx = chronological_split(dates, test_size=test_size)
    if len(train_idx) == 0 or len(test_idx) == 0:
        raise ValueError("Not enough resolved trades to form a chronological train/test split.")

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    model = train_model(X_train, y_train, model_type=model_type)
    report = evaluate_model(model, X_test, y_test)
    return model, report
