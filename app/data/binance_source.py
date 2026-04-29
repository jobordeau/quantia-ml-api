from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pandas as pd

from app.config import get_settings
from app.data.base import CandleDataSource
from app.utils import get_logger

log = get_logger(__name__)

_INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

_KLINES_LIMIT = 1000


class BinanceSource(CandleDataSource):
    def __init__(self) -> None:
        settings = get_settings()
        self._base = settings.binance_base_url.rstrip("/")
        self._timeout = settings.binance_request_timeout_seconds

    def _fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list]:
        url = f"{self._base}/api/v3/klines"
        out: list[list] = []
        cursor = start_ms

        with httpx.Client(timeout=self._timeout) as client:
            while cursor < end_ms:
                params = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": _KLINES_LIMIT,
                }
                r = client.get(url, params=params)
                r.raise_for_status()
                batch = r.json()
                if not batch:
                    break
                out.extend(batch)
                last_open = batch[-1][0]
                step = _INTERVAL_MS.get(interval, _INTERVAL_MS["1m"])
                next_cursor = last_open + step
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(batch) < _KLINES_LIMIT:
                    break

        return out

    @staticmethod
    def _to_dataframe(klines: list[list]) -> pd.DataFrame:
        if not klines:
            return pd.DataFrame(
                columns=[
                    "timestamp_utc", "open", "high", "low", "close",
                    "volume", "quote_volume", "nb_trades",
                ]
            )

        df = pd.DataFrame(
            klines,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "nb_trades",
                "taker_buy_base", "taker_buy_quote", "ignore",
            ],
        )
        df["timestamp_utc"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for col in ("open", "high", "low", "close", "volume", "quote_volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["nb_trades"] = pd.to_numeric(df["nb_trades"], errors="coerce").fillna(0).astype(int)

        return df[
            [
                "timestamp_utc", "open", "high", "low", "close",
                "volume", "quote_volume", "nb_trades",
            ]
        ].reset_index(drop=True)

    def fetch_recent(self, symbol: str, days: int, interval: str = "1m") -> pd.DataFrame:
        end = datetime.now(UTC)
        start = end - timedelta(days=max(days, 1))
        return self.fetch_range(symbol, start, end, interval)

    def fetch_range(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> pd.DataFrame:
        if interval not in _INTERVAL_MS:
            raise ValueError(f"Unsupported interval: {interval}")

        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if end <= start:
            raise ValueError("end must be strictly after start")

        log.info("Binance fetch_range %s [%s -> %s]", symbol, start.isoformat(), end.isoformat())
        klines = self._fetch_klines(
            symbol,
            interval,
            int(start.timestamp() * 1000),
            int(end.timestamp() * 1000),
        )
        df = self._to_dataframe(klines)
        log.info("Binance returned %d rows for %s", len(df), symbol)
        return df

    def fetch_last_candle(self, symbol: str) -> pd.DataFrame:
        url = f"{self._base}/api/v3/klines"
        params = {"symbol": symbol.upper(), "interval": "1m", "limit": 1}
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return self._to_dataframe(r.json())
