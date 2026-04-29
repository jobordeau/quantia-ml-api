from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd
import xgboost as xgb

from app.config import get_settings
from app.features import FEATURE_COLUMNS, add_all_features
from app.utils import get_logger

log = get_logger(__name__)


class ModelNotFoundError(RuntimeError):
    pass


class Predictor:
    def __init__(self, model_path: Path) -> None:
        self._path = Path(model_path)
        self._booster: xgb.Booster | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def is_loaded(self) -> bool:
        return self._booster is not None

    def load(self) -> None:
        if not self._path.exists():
            raise ModelNotFoundError(f"Model file not found at {self._path}")
        booster = xgb.Booster()
        booster.load_model(str(self._path))
        with self._lock:
            self._booster = booster
        log.info("XGBoost model loaded from %s", self._path)

    def reload(self) -> None:
        self.load()

    def predict_proba_up(self, df: pd.DataFrame) -> pd.Series:
        if self._booster is None:
            self.load()

        enriched = add_all_features(df)
        enriched = enriched.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)

        if enriched.empty:
            return pd.Series([], dtype=float)

        dmat = xgb.DMatrix(enriched[FEATURE_COLUMNS])
        preds = self._booster.predict(dmat)
        return pd.Series(preds, index=enriched.index, name="prob_up")


_predictor_singleton: Predictor | None = None
_predictor_lock = threading.Lock()


def get_predictor() -> Predictor:
    global _predictor_singleton
    if _predictor_singleton is not None:
        return _predictor_singleton
    with _predictor_lock:
        if _predictor_singleton is None:
            _predictor_singleton = Predictor(get_settings().model_path)
            try:
                _predictor_singleton.load()
            except ModelNotFoundError as e:
                log.warning("Predictor created but model is not loaded: %s", e)
    return _predictor_singleton
