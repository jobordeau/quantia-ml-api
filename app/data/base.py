from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class CandleDataSource(ABC):
    @abstractmethod
    def fetch_recent(self, symbol: str, days: int, interval: str = "1m") -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def fetch_range(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def fetch_last_candle(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError
