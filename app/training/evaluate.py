from __future__ import annotations

from math import log
from pathlib import Path

import pandas as pd
import xgboost as xgb

from app.features import FEATURE_COLUMNS
from app.utils import get_logger

logger = get_logger(__name__)


def _log_loss(y_true: list[int], y_pred: list[float], eps: float = 1e-15) -> float:
    if not y_true:
        return float("inf")
    clipped = [min(max(p, eps), 1 - eps) for p in y_pred]
    return -sum(
        y * log(p) + (1 - y) * log(1 - p)
        for y, p in zip(y_true, clipped, strict=False)
    ) / len(y_true)


def evaluate_model(df: pd.DataFrame, model_path: Path | str) -> dict[str, float]:
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    clean = df.dropna().copy()
    if clean.empty:
        raise ValueError("Evaluation dataframe is empty")

    X = clean[FEATURE_COLUMNS]
    y_true = clean["direction"].astype(int).tolist()

    booster = xgb.Booster()
    booster.load_model(str(model_path))
    y_pred = booster.predict(xgb.DMatrix(X)).tolist()

    threshold = 0.5
    tp = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 1 and yp >= threshold)
    tn = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 0 and yp < threshold)
    fp = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 0 and yp >= threshold)
    fn = sum(1 for yt, yp in zip(y_true, y_pred, strict=False) if yt == 1 and yp < threshold)

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    metrics = {
        "logloss": _log_loss(y_true, y_pred),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_samples": float(total),
        "true_positive": float(tp),
        "true_negative": float(tn),
        "false_positive": float(fp),
        "false_negative": float(fn),
    }
    logger.info("Evaluation: %s", metrics)
    return metrics
