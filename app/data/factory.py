from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.data.base import CandleDataSource
from app.utils import get_logger

log = get_logger(__name__)


@lru_cache
def get_data_source() -> CandleDataSource:
    source = get_settings().data_source
    log.info("Initialising data source: %s", source)

    if source == "binance":
        from app.data.binance_source import BinanceSource
        return BinanceSource()
    if source == "bigquery":
        from app.data.bigquery_source import BigQuerySource
        return BigQuerySource()
    raise ValueError(f"Unknown DATA_SOURCE: {source}")
