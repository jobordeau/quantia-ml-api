from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import PredictionResponse
from app.config import get_settings
from app.data import get_data_source
from app.models import get_predictor, suggest_levels
from app.models.predictor import ModelNotFoundError
from app.utils import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/prediction", tags=["prediction"])


@router.get("/latest", response_model=PredictionResponse)
def predict_latest(
    symbol: str = Query("BTCUSDT", min_length=3),
    days: int = Query(2, ge=1, le=10),
) -> PredictionResponse:
    settings = get_settings()
    sym = symbol.upper()

    df = get_data_source().fetch_recent(sym, days=days, interval="1m")
    if df.empty or len(df) < settings.risk_atr_window + 30:
        raise HTTPException(
            status_code=503,
            detail=f"Not enough candles available for {sym} (got {len(df)})",
        )

    try:
        probs = get_predictor().predict_proba_up(df)
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Model artefact not loaded. Train one first via POST /run_ml_pipeline.",
        ) from exc

    if probs.empty:
        raise HTTPException(status_code=503, detail="No prediction could be produced.")

    last_prob = float(probs.iloc[-1])
    side_label = "LONG" if last_prob >= 0.5 else "SHORT"
    confidence = abs(last_prob - 0.5) * 2

    levels = suggest_levels(df, side=side_label, risk_multiple=1.0)

    return PredictionResponse(
        symbol=sym,
        timestamp=datetime.now(UTC),
        prob_up=last_prob,
        signal=side_label,
        confidence=confidence,
        entry=levels.entry,
        stop_loss=levels.stop_loss,
        take_profit=levels.take_profit,
        note=f"atr14={levels.atr}",
    )
