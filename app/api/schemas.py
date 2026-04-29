from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: str
    utc: datetime
    model_loaded: bool
    data_source: str
    version: str


class CandleRow(BaseModel):
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    nb_trades: int


class LastCandleResponse(BaseModel):
    symbol: str
    timestamp_utc: datetime
    price_usdt: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleHistoryResponse(BaseModel):
    symbol: str
    interval: str
    days: int
    count: int
    data: list[CandleRow]


class PredictionResponse(BaseModel):
    symbol: str
    timestamp: datetime
    prob_up: float = Field(..., ge=0.0, le=1.0)
    signal: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    entry: float
    stop_loss: float
    take_profit: float
    note: str | None = None


class TradeSuggestion(BaseModel):
    symbol: str
    side: str
    entry_price: float = Field(..., alias="EntryPrice")
    stop_loss: float = Field(..., alias="StopLoss")
    take_profit: float = Field(..., alias="TakeProfit")
    position_size: float = Field(..., alias="PositionSize")
    confidence: float = Field(..., alias="Confidence")
    timestamp: datetime = Field(..., alias="Timestamp")

    model_config = {"populate_by_name": True}


class PatternMatch(BaseModel):
    sequence: list[int]
    start_timestamp: datetime
    end_timestamp: datetime
    bias: float
    direction: str


class ShortTermForecast(BaseModel):
    direction: str
    probability: float
    bias: float


class PatternResponse(BaseModel):
    symbol: str
    start_date: datetime
    end_date: datetime
    patterns_detected: list[PatternMatch]
    short_term_forecast: ShortTermForecast | None = None


class ClassicPatternMatch(BaseModel):
    name: str
    direction: str
    timestamp: datetime


class ClassicPatternResponse(BaseModel):
    symbol: str
    start_date: datetime
    end_date: datetime
    patterns_detected: list[ClassicPatternMatch]


class CandleWithType(CandleRow):
    candle_type: int


class LoadDataPatternsResponse(BaseModel):
    symbol: str
    start_date: datetime
    end_date: datetime
    count: int
    data: list[CandleWithType]


class PipelineRequest(BaseModel):
    model_config = {"protected_namespaces": ()}

    mode: str = Field(default="full")
    symbol: str = Field(default="BTCUSDT")
    days: int = Field(default=3, ge=1, le=30)
    model_path: str | None = None


class ModelMetricsResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_path: str
    metrics: dict


class RefreshModelResponse(BaseModel):
    promoted: bool
    new_metrics: dict
    old_metrics: dict
