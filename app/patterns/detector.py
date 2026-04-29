from __future__ import annotations

import ast
import threading
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.utils import get_logger

log = get_logger(__name__)


class PatternDetector:
    def __init__(self, patterns_path: Path) -> None:
        self._path = Path(patterns_path)
        self._patterns: dict[tuple[int, ...], dict] | None = None
        self._lock = threading.Lock()

    def load(self) -> None:
        if not self._path.exists():
            log.warning("Patterns file not found at %s — detector will be empty", self._path)
            with self._lock:
                self._patterns = {}
            return

        df = pd.read_csv(self._path)
        result: dict[tuple[int, ...], dict] = {}
        for _, row in df.iterrows():
            try:
                seq = tuple(ast.literal_eval(row["sequence"]))
            except (ValueError, SyntaxError):
                continue
            result[seq] = {
                "bias":          float(row.get("bias", 0.0)),
                "bullish_ratio": float(row.get("bullish_ratio", 0.0)),
                "bearish_ratio": float(row.get("bearish_ratio", 0.0)),
                "total":         int(row.get("total", 0)),
            }
        with self._lock:
            self._patterns = result
        log.info("Loaded %d significant patterns", len(result))

    @property
    def patterns(self) -> dict[tuple[int, ...], dict]:
        if self._patterns is None:
            self.load()
        return self._patterns or {}

    def find_matches(
        self,
        df: pd.DataFrame,
        max_len: int = 3,
        max_results: int = 5,
        min_gap_minutes: int = 2,
    ) -> list[dict]:
        if df.empty or "candle_type" not in df.columns:
            return []

        candle_ids = df["candle_type"].tolist()
        timestamps = pd.to_datetime(df["timestamp_utc"]).tolist()
        known = self.patterns
        matches: list[dict] = []

        for i in range(len(candle_ids)):
            for length in range(1, max_len + 1):
                end = i + length
                if end > len(candle_ids):
                    break
                seq = tuple(candle_ids[i:end])
                if seq not in known:
                    continue
                meta = known[seq]
                bias = meta["bias"]
                direction = (
                    "bullish" if bias > 0.05
                    else "bearish" if bias < -0.05
                    else "neutral"
                )
                matches.append(
                    {
                        "sequence":        list(seq),
                        "start_timestamp": timestamps[i].isoformat(),
                        "end_timestamp":   timestamps[end - 1].isoformat(),
                        "bias":            bias,
                        "direction":       direction,
                    }
                )

        matches.sort(key=lambda m: abs(m["bias"]), reverse=True)

        filtered: list[dict] = []
        seen: set = set()
        last_end_ts: pd.Timestamp | None = None
        for m in matches:
            key = (tuple(m["sequence"]), m["direction"])
            if key in seen:
                continue
            start_ts = pd.to_datetime(m["start_timestamp"])
            if last_end_ts is not None:
                if (start_ts - last_end_ts).total_seconds() / 60 < min_gap_minutes:
                    continue
            filtered.append(m)
            seen.add(key)
            last_end_ts = pd.to_datetime(m["end_timestamp"])
            if len(filtered) >= max_results:
                break

        return filtered


_detector_singleton: PatternDetector | None = None
_detector_lock = threading.Lock()


def get_pattern_detector() -> PatternDetector:
    global _detector_singleton
    if _detector_singleton is not None:
        return _detector_singleton
    with _detector_lock:
        if _detector_singleton is None:
            _detector_singleton = PatternDetector(get_settings().patterns_path)
            _detector_singleton.load()
    return _detector_singleton


def detect_classic_patterns(df: pd.DataFrame, atr_min_pct: float = 0.05) -> list[dict]:
    if df.empty or len(df) < 3:
        return []

    out = df.copy().reset_index(drop=True)
    body = (out["close"] - out["open"]).abs()
    rng = (out["high"] - out["low"]).replace(0, 1e-9)
    upper = out["high"] - out[["open", "close"]].max(axis=1)
    lower = out[["open", "close"]].min(axis=1) - out["low"]
    body_ratio = body / rng

    timestamps = pd.to_datetime(out["timestamp_utc"]).tolist()
    closes = out["close"].tolist()
    opens = out["open"].tolist()

    rolling_atr = (out["high"] - out["low"]).rolling(14, min_periods=1).mean()
    threshold = out["close"] * (atr_min_pct / 100.0)
    significant = rolling_atr >= threshold

    detected: list[dict] = []

    for i in range(2, len(out)):
        if not bool(significant.iloc[i]):
            continue
        ts = timestamps[i].isoformat()

        if body_ratio.iloc[i] < 0.1 and rng.iloc[i] > 0:
            detected.append({
                "name": "doji",
                "direction": "neutral",
                "timestamp": ts,
            })
            continue

        if (
            lower.iloc[i] > 2 * body.iloc[i]
            and upper.iloc[i] < body.iloc[i]
            and closes[i] > opens[i]
        ):
            detected.append({"name": "hammer", "direction": "bullish", "timestamp": ts})
            continue

        if (
            upper.iloc[i] > 2 * body.iloc[i]
            and lower.iloc[i] < body.iloc[i]
            and closes[i] < opens[i]
        ):
            detected.append({"name": "shooting_star", "direction": "bearish", "timestamp": ts})
            continue

        prev_body = abs(closes[i - 1] - opens[i - 1])
        if (
            closes[i - 1] < opens[i - 1]
            and closes[i] > opens[i]
            and opens[i] <= closes[i - 1]
            and closes[i] >= opens[i - 1]
            and body.iloc[i] > prev_body
        ):
            detected.append({"name": "bullish_engulfing", "direction": "bullish", "timestamp": ts})
            continue

        if (
            closes[i - 1] > opens[i - 1]
            and closes[i] < opens[i]
            and opens[i] >= closes[i - 1]
            and closes[i] <= opens[i - 1]
            and body.iloc[i] > prev_body
        ):
            detected.append({"name": "bearish_engulfing", "direction": "bearish", "timestamp": ts})
            continue

    return detected
