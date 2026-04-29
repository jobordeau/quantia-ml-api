from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.data import get_data_source
from app.features import add_all_features, build_targets
from app.models.predictor import get_predictor
from app.training.evaluate import evaluate_model
from app.training.train import train_direction_model
from app.utils import get_logger

log = get_logger(__name__)


def run_training_pipeline(
    symbol: str | None = None,
    days: int = 3,
    model_path: Path | None = None,
    promote_only_if_better: bool = True,
) -> dict:
    settings = get_settings()
    symbol = (symbol or settings.default_symbol).upper()
    final_path = Path(model_path or settings.model_path)
    temp_path = final_path.with_name(final_path.stem + "_candidate.json")

    started = datetime.now(UTC)
    log.info("Pipeline start: symbol=%s days=%d output=%s", symbol, days, final_path)

    df = get_data_source().fetch_recent(symbol=symbol, days=days, interval="1m")
    df = add_all_features(df)
    df = build_targets(df)

    train_direction_model(df, output_path=temp_path)
    new_metrics = evaluate_model(df, temp_path)

    promoted = False
    old_metrics: dict = {}
    if final_path.exists():
        try:
            old_metrics = evaluate_model(df, final_path)
        except Exception as exc:
            log.warning("Old model evaluation failed: %s", exc)

    if (
        not promote_only_if_better
        or not old_metrics
        or new_metrics["logloss"] < old_metrics.get("logloss", float("inf"))
    ):
        os.replace(temp_path, final_path)
        promoted = True
        log.info("Candidate model promoted to %s", final_path)
        try:
            get_predictor().reload()
        except Exception as exc:
            log.warning("Predictor reload failed: %s", exc)
    else:
        temp_path.unlink(missing_ok=True)
        log.info("Candidate rejected — old model retained")

    return {
        "symbol": symbol,
        "days": days,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "rows_used": int(len(df)),
        "promoted": promoted,
        "old_metrics": old_metrics,
        "new_metrics": new_metrics,
    }
