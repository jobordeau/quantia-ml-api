from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from app.config import get_settings
from app.data.base import CandleDataSource
from app.utils import get_logger

log = get_logger(__name__)


class BigQuerySource(CandleDataSource):
    def __init__(self) -> None:
        try:
            from google.cloud import bigquery
        except ImportError as e:
            raise RuntimeError(
                "google-cloud-bigquery is not installed. Install it or switch DATA_SOURCE=binance."
            ) from e

        settings = get_settings()
        if not (settings.bigquery_project and settings.bigquery_dataset and settings.bigquery_table):
            raise RuntimeError(
                "BigQuery source requires BIGQUERY_PROJECT, BIGQUERY_DATASET and BIGQUERY_TABLE env vars."
            )

        self._project = settings.bigquery_project
        self._dataset = settings.bigquery_dataset
        self._table = settings.bigquery_table
        self._client = bigquery.Client(project=self._project)
        log.info(
            "BigQuery client ready for %s.%s.%s",
            self._project, self._dataset, self._table,
        )

    @property
    def _fqtn(self) -> str:
        return f"`{self._project}.{self._dataset}.{self._table}`"

    def _execute(self, query: str, params: dict) -> pd.DataFrame:
        from google.cloud import bigquery as bq

        log.info("BigQuery executing parameterised query")
        job_config = bq.QueryJobConfig(
            query_parameters=[
                bq.ScalarQueryParameter(name, type_, value)
                for name, (type_, value) in params.items()
            ]
        )
        df = self._client.query(query, job_config=job_config).to_dataframe()
        if "timestamp_utc" in df.columns:
            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        log.info("BigQuery returned %d rows", len(df))
        return df

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
        if interval != "1m":
            raise ValueError("BigQuery source currently supports only 1m candles")

        query = f"""
            SELECT timestamp_utc, open, high, low, close, volume,
                   quote_volume, nb_trades
            FROM {self._fqtn}
            WHERE symbol = @symbol
              AND timestamp_utc >= @start_ts
              AND timestamp_utc <= @end_ts
            ORDER BY timestamp_utc ASC
        """
        return self._execute(
            query,
            {
                "symbol":   ("STRING", symbol.upper()),
                "start_ts": ("TIMESTAMP", start),
                "end_ts":   ("TIMESTAMP", end),
            },
        )

    def fetch_last_candle(self, symbol: str) -> pd.DataFrame:
        query = f"""
            SELECT timestamp_utc, open, high, low, close, volume,
                   quote_volume, nb_trades
            FROM {self._fqtn}
            WHERE symbol = @symbol
            ORDER BY timestamp_utc DESC
            LIMIT 1
        """
        return self._execute(query, {"symbol": ("STRING", symbol.upper())})
