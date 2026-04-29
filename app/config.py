from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        protected_namespaces=("settings_",),
    )

    app_name: str = "Quantia ML API"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    data_source: Literal["binance", "bigquery"] = Field(
        default="binance",
        description="Where to read OHLCV candles from. 'binance' needs no credentials.",
    )

    binance_base_url: str = "https://api.binance.com"
    binance_request_timeout_seconds: float = 15.0

    bigquery_project: str | None = None
    bigquery_dataset: str | None = None
    bigquery_table: str | None = None
    google_application_credentials: str | None = None

    artifacts_dir: Path = Field(default=Path("artifacts"))
    model_filename: str = "xgb_direction.json"
    patterns_filename: str = "significant_patterns.csv"

    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    default_symbol: str = "BTCUSDT"
    supported_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])

    risk_atr_window: int = 14
    risk_atr_stop_multiplier: float = 1.5
    risk_atr_take_multiplier: float = 3.0

    @property
    def model_path(self) -> Path:
        return self.artifacts_dir / "models" / self.model_filename

    @property
    def patterns_path(self) -> Path:
        return self.artifacts_dir / "patterns" / self.patterns_filename


@lru_cache
def get_settings() -> Settings:
    return Settings()
