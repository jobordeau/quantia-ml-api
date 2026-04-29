from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import TradeSuggestion
from app.config import get_settings
from app.data import get_data_source
from app.models import get_predictor, suggest_levels
from app.models.predictor import ModelNotFoundError

router = APIRouter(prefix="/trade", tags=["trade"])


@router.get("/suggest", response_model=TradeSuggestion)
def suggest(
    symbol: str = Query(..., min_length=3),
    risk_multiple: float = Query(1.0, ge=0.1, le=10.0),
) -> TradeSuggestion:
    settings = get_settings()
    sym = symbol.upper()

    df = get_data_source().fetch_recent(sym, days=2, interval="1m")
    if df.empty or len(df) < settings.risk_atr_window + 30:
        raise HTTPException(status_code=503, detail=f"Not enough candles for {sym}")

    try:
        probs = get_predictor().predict_proba_up(df)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Model not loaded") from exc

    if probs.empty:
        raise HTTPException(status_code=503, detail="No prediction could be produced")

    last_prob = float(probs.iloc[-1])
    side = "LONG" if last_prob >= 0.5 else "SHORT"
    confidence = abs(last_prob - 0.5) * 2

    levels = suggest_levels(df, side=side, risk_multiple=risk_multiple)

    return TradeSuggestion(
        symbol=sym,
        side=side,
        EntryPrice=levels.entry,
        StopLoss=levels.stop_loss,
        TakeProfit=levels.take_profit,
        PositionSize=round(confidence, 4),
        Confidence=round(confidence, 4),
        Timestamp=datetime.now(UTC),
    )
