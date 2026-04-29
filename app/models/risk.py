from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import ta

from app.config import get_settings


@dataclass(frozen=True)
class RiskLevels:
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    atr: float


def compute_atr(df: pd.DataFrame, window: int = 14) -> float:
    if len(df) < window + 1:
        return 0.0
    indicator = ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=window
    )
    series = indicator.average_true_range().dropna()
    if series.empty:
        return 0.0
    return float(series.iloc[-1])


def suggest_levels(
    df: pd.DataFrame,
    side: str,
    risk_multiple: float = 1.0,
) -> RiskLevels:
    settings = get_settings()
    atr = compute_atr(df, window=settings.risk_atr_window)
    entry = float(df["close"].iloc[-1])

    stop_dist = settings.risk_atr_stop_multiplier * atr * max(risk_multiple, 0.1)
    take_dist = settings.risk_atr_take_multiplier * atr * max(risk_multiple, 0.1)

    if atr == 0.0:
        stop_dist = entry * 0.005 * max(risk_multiple, 0.1)
        take_dist = entry * 0.010 * max(risk_multiple, 0.1)

    side_normalized = side.upper()
    if side_normalized in ("LONG", "BUY"):
        sl = entry - stop_dist
        tp = entry + take_dist
        side_out = "LONG"
    elif side_normalized in ("SHORT", "SELL"):
        sl = entry + stop_dist
        tp = entry - take_dist
        side_out = "SHORT"
    else:
        raise ValueError(f"Unknown side: {side}")

    return RiskLevels(
        side=side_out,
        entry=round(entry, 4),
        stop_loss=round(sl, 4),
        take_profit=round(tp, 4),
        atr=round(atr, 6),
    )
