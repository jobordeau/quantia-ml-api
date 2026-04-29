from __future__ import annotations

import pandas as pd
import ta

FEATURE_COLUMNS: list[str] = [
    "open", "high", "low", "close", "volume", "quote_volume", "nb_trades",
    "sma_5", "sma_10", "ema_5", "ema_10", "rsi_14",
    "macd", "macd_signal", "macd_diff",
    "bb_upper", "bb_lower", "bb_width",
    "atr_14",
]


def add_all_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in ("quote_volume", "nb_trades"):
        if col not in out.columns:
            out[col] = 0.0

    out["sma_5"]  = out["close"].rolling(window=5).mean()
    out["sma_10"] = out["close"].rolling(window=10).mean()
    out["ema_5"]  = out["close"].ewm(span=5,  adjust=False).mean()
    out["ema_10"] = out["close"].ewm(span=10, adjust=False).mean()

    out["rsi_14"] = ta.momentum.RSIIndicator(close=out["close"], window=14).rsi()

    macd = ta.trend.MACD(close=out["close"])
    out["macd"]        = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_diff"]   = macd.macd_diff()

    bb = ta.volatility.BollingerBands(close=out["close"], window=20, window_dev=2)
    out["bb_upper"] = bb.bollinger_hband()
    out["bb_lower"] = bb.bollinger_lband()
    out["bb_width"] = out["bb_upper"] - out["bb_lower"]

    atr = ta.volatility.AverageTrueRange(
        high=out["high"], low=out["low"], close=out["close"], window=14
    )
    out["atr_14"] = atr.average_true_range()

    return out


def select_features(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")
    return df[FEATURE_COLUMNS].copy()
