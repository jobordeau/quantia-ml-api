from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans2, whiten


def compute_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    body = (df["close"] - df["open"]).abs()
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    rng = (df["high"] - df["low"]).replace(0, 1e-9)

    rolling_mean = df["volume"].rolling(1000, min_periods=1).mean()
    rolling_std = df["volume"].rolling(1000, min_periods=1).std(ddof=0)

    return pd.DataFrame(
        {
            "body_size": body,
            "upper_wick": upper,
            "lower_wick": lower,
            "body_ratio": body / rng,
            "upper_ratio": upper / rng,
            "lower_ratio": lower / rng,
            "direction": np.sign(df["close"] - df["open"]),
            "volume_zscore": (df["volume"] - rolling_mean) / rolling_std,
        }
    ).fillna(0)


def assign_candle_types(df: pd.DataFrame, n_clusters: int = 10) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["candle_type"] = []
        return out

    features = compute_candle_features(out)
    if len(features) < n_clusters:
        out["candle_type"] = [0] * len(out)
        return out

    matrix = features.values.astype(np.float32)
    whitened = whiten(matrix)
    _, labels = kmeans2(whitened, k=n_clusters, minit="++", seed=42)
    out["candle_type"] = labels.astype(int)
    return out
