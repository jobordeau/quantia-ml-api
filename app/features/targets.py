from __future__ import annotations

import pandas as pd


def build_targets(df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    out = df.copy()
    out["next_close"] = out["close"].shift(-horizon)
    out["return_next"] = (out["next_close"] - out["close"]) / out["close"]
    out["direction"] = (out["return_next"] > 0).astype(int)
    return out
