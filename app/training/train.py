from __future__ import annotations

from pathlib import Path

import pandas as pd
import xgboost as xgb

from app.features import FEATURE_COLUMNS
from app.utils import get_logger

log = get_logger(__name__)


def train_direction_model(
    df: pd.DataFrame,
    output_path: Path | str,
    num_boost_round: int = 100,
    params: dict | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clean = df.dropna().copy()
    if clean.empty:
        raise ValueError("Training dataframe is empty after dropping NaN rows")

    missing = [c for c in FEATURE_COLUMNS + ["direction"] if c not in clean.columns]
    if missing:
        raise ValueError(f"Missing columns for training: {missing}")

    X = clean[FEATURE_COLUMNS]
    y = clean["direction"]

    dtrain = xgb.DMatrix(X, label=y)
    config = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "verbosity": 1,
    }
    if params:
        config.update(params)

    log.info("Training XGBoost direction model on %d rows", len(clean))
    booster = xgb.train(config, dtrain, num_boost_round=num_boost_round)
    booster.save_model(str(output_path))
    log.info("Model saved to %s", output_path)

    return output_path
