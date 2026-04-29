from app.features import FEATURE_COLUMNS, add_all_features, build_targets
from app.models import compute_atr, suggest_levels


def test_add_all_features_columns(candles_df):
    enriched = add_all_features(candles_df)
    for col in FEATURE_COLUMNS:
        assert col in enriched.columns


def test_build_targets(candles_df):
    enriched = build_targets(add_all_features(candles_df))
    assert "next_close" in enriched.columns
    assert "return_next" in enriched.columns
    assert "direction" in enriched.columns
    direction = enriched["direction"].dropna().unique().tolist()
    assert set(direction).issubset({0, 1})


def test_compute_atr_positive(candles_df):
    atr = compute_atr(candles_df, window=14)
    assert atr > 0


def test_suggest_levels_long(candles_df):
    levels = suggest_levels(candles_df, side="LONG", risk_multiple=1.0)
    assert levels.side == "LONG"
    assert levels.stop_loss < levels.entry < levels.take_profit


def test_suggest_levels_short(candles_df):
    levels = suggest_levels(candles_df, side="SHORT", risk_multiple=1.0)
    assert levels.side == "SHORT"
    assert levels.take_profit < levels.entry < levels.stop_loss
