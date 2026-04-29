from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.schemas import (
    CandleHistoryResponse,
    CandleRow,
    LastCandleResponse,
)
from app.data import get_data_source

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/{symbol}/last_candle", response_model=LastCandleResponse)
def last_candle(symbol: str = Path(..., min_length=3)) -> LastCandleResponse:
    df = get_data_source().fetch_last_candle(symbol.upper())
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
    last = df.iloc[-1]
    return LastCandleResponse(
        symbol=symbol.upper(),
        timestamp_utc=last["timestamp_utc"].to_pydatetime(),
        price_usdt=float(last["close"]),
        open=float(last["open"]),
        high=float(last["high"]),
        low=float(last["low"]),
        close=float(last["close"]),
        volume=float(last["volume"]),
    )


@router.get("/{symbol}", response_model=CandleHistoryResponse)
def history(
    symbol: str = Path(..., min_length=3),
    days: int = Query(7, ge=1, le=60),
    interval: str = Query("1m"),
    raw: bool | None = Query(False, description="Reserved; kept for compatibility"),
) -> CandleHistoryResponse:
    df = get_data_source().fetch_recent(symbol.upper(), days=days, interval=interval)
    rows = [
        CandleRow(
            timestamp_utc=r["timestamp_utc"].to_pydatetime(),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            quote_volume=float(r.get("quote_volume", 0.0) or 0.0),
            nb_trades=int(r.get("nb_trades", 0) or 0),
        )
        for _, r in df.iterrows()
    ]
    return CandleHistoryResponse(
        symbol=symbol.upper(),
        interval=interval,
        days=days,
        count=len(rows),
        data=rows,
    )
