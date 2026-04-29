from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    CandleWithType,
    ClassicPatternMatch,
    ClassicPatternResponse,
    LoadDataPatternsResponse,
    PatternMatch,
    PatternResponse,
    ShortTermForecast,
)
from app.data import get_data_source
from app.patterns import (
    assign_candle_types,
    detect_classic_patterns,
    get_pattern_detector,
)

router = APIRouter(prefix="/pattern", tags=["pattern"])

_FMT = "%Y-%m-%dT%H:%M"


def _parse_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    try:
        start_utc = datetime.strptime(start_date, _FMT).replace(tzinfo=UTC)
        end_utc = datetime.strptime(end_date, _FMT).replace(tzinfo=UTC)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {exc}") from exc
    if end_utc <= start_utc:
        raise HTTPException(status_code=400, detail="end_date must be strictly after start_date")
    return start_utc, end_utc


@router.get("/load-data", response_model=LoadDataPatternsResponse)
def load_data(
    symbol: str = Query(..., min_length=3),
    start_date: str = Query(..., description="YYYY-MM-DDTHH:MM (UTC)"),
    end_date:   str = Query(..., description="YYYY-MM-DDTHH:MM (UTC)"),
):
    start_utc, end_utc = _parse_range(start_date, end_date)
    df = get_data_source().fetch_range(symbol.upper(), start_utc, end_utc, interval="1m")
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    df = assign_candle_types(df)

    rows = [
        CandleWithType(
            timestamp_utc=r["timestamp_utc"].to_pydatetime(),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            quote_volume=float(r.get("quote_volume", 0.0) or 0.0),
            nb_trades=int(r.get("nb_trades", 0) or 0),
            candle_type=int(r.get("candle_type", 0)),
        )
        for _, r in df.iterrows()
    ]
    return LoadDataPatternsResponse(
        symbol=symbol.upper(),
        start_date=start_utc,
        end_date=end_utc,
        count=len(rows),
        data=rows,
    )


@router.get("/load-data-patterns", response_model=PatternResponse)
def load_data_patterns(
    symbol: str = Query(..., min_length=3),
    start_date: str = Query(...),
    end_date:   str = Query(...),
):
    start_utc, end_utc = _parse_range(start_date, end_date)
    df = get_data_source().fetch_range(symbol.upper(), start_utc, end_utc, interval="1m")
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    df = assign_candle_types(df)

    raw_matches = get_pattern_detector().find_matches(df)
    matches = [PatternMatch(**m) for m in raw_matches]

    forecast = None
    if matches:
        last = matches[-1]
        forecast = ShortTermForecast(
            direction=last.direction,
            probability=min(1.0, max(0.5, 0.5 + abs(last.bias))),
            bias=round(last.bias, 3),
        )

    return PatternResponse(
        symbol=symbol.upper(),
        start_date=start_utc,
        end_date=end_utc,
        patterns_detected=matches,
        short_term_forecast=forecast,
    )


@router.get("/load-data-patterns-classic", response_model=ClassicPatternResponse)
def load_classic_patterns(
    symbol: str = Query(..., min_length=3),
    start_date: str = Query(...),
    end_date:   str = Query(...),
    atr_min_pct: float = Query(0.05, ge=0.0, le=10.0),
):
    start_utc, end_utc = _parse_range(start_date, end_date)
    df = get_data_source().fetch_range(symbol.upper(), start_utc, end_utc, interval="1m")
    df = df.sort_values("timestamp_utc").reset_index(drop=True)

    raw_matches = detect_classic_patterns(df, atr_min_pct=atr_min_pct)
    matches = [ClassicPatternMatch(**m) for m in raw_matches]

    return ClassicPatternResponse(
        symbol=symbol.upper(),
        start_date=start_utc,
        end_date=end_utc,
        patterns_detected=matches,
    )
