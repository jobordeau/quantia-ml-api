from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.data.base import CandleDataSource
from app.data.factory import get_data_source as real_get_data_source


def _generate_candles(
    n: int = 500,
    start: datetime | None = None,
    seed: int = 42,
    base_price: float = 100.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = start or datetime(2025, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=i) for i in range(n)]

    returns = rng.normal(0, 0.001, size=n)
    close = base_price * np.cumprod(1 + returns)
    open_ = np.concatenate([[base_price], close[:-1]])
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.0015, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.0015, n))
    volume = rng.uniform(0.5, 5.0, n)
    quote_volume = volume * close

    return pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(timestamps, utc=True),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "quote_volume": quote_volume,
            "nb_trades": rng.integers(50, 500, n),
        }
    )


class FakeDataSource(CandleDataSource):
    def __init__(self) -> None:
        self._df = _generate_candles(n=600)

    def fetch_recent(self, symbol: str, days: int, interval: str = "1m") -> pd.DataFrame:
        return self._df.copy()

    def fetch_range(self, symbol: str, start, end, interval: str = "1m") -> pd.DataFrame:
        return self._df.copy()

    def fetch_last_candle(self, symbol: str) -> pd.DataFrame:
        return self._df.tail(1).copy().reset_index(drop=True)


@pytest.fixture(autouse=True)
def fake_data_source(monkeypatch):
    real_get_data_source.cache_clear()
    fake = FakeDataSource()
    monkeypatch.setattr("app.data.factory.get_data_source", lambda: fake)
    monkeypatch.setattr("app.data.get_data_source", lambda: fake)
    monkeypatch.setattr("app.api.routes.data.get_data_source", lambda: fake)
    monkeypatch.setattr("app.api.routes.prediction.get_data_source", lambda: fake)
    monkeypatch.setattr("app.api.routes.pattern.get_data_source", lambda: fake)
    monkeypatch.setattr("app.api.routes.trade.get_data_source", lambda: fake)
    monkeypatch.setattr("app.api.routes.model.get_data_source", lambda: fake)
    monkeypatch.setattr("app.training.pipeline.get_data_source", lambda: fake)
    yield fake


@pytest.fixture
def client():
    from app.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def candles_df() -> pd.DataFrame:
    return _generate_candles(n=300)
