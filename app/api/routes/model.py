from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    ModelMetricsResponse,
    PipelineRequest,
    RefreshModelResponse,
)
from app.config import get_settings
from app.data import get_data_source
from app.features import add_all_features, build_targets
from app.training.evaluate import evaluate_model
from app.training.pipeline import run_training_pipeline
from app.utils import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["model"])


@router.post("/refresh-model", response_model=RefreshModelResponse)
def refresh_model() -> RefreshModelResponse:
    result = run_training_pipeline(
        symbol=get_settings().default_symbol,
        days=3,
        promote_only_if_better=True,
    )
    return RefreshModelResponse(
        promoted=result["promoted"],
        new_metrics=result["new_metrics"],
        old_metrics=result["old_metrics"],
    )


@router.post("/run_ml_pipeline")
def run_ml_pipeline(request: PipelineRequest) -> dict:
    return run_training_pipeline(
        symbol=request.symbol,
        days=request.days,
        model_path=request.model_path,
        promote_only_if_better=(request.mode != "force"),
    )


@router.get("/get_model_metrics", response_model=ModelMetricsResponse)
def get_model_metrics(
    model: str | None = Query(None, description="Optional path to a model artefact"),
    symbol: str = Query("BTCUSDT", min_length=3),
    days: int = Query(2, ge=1, le=30),
) -> ModelMetricsResponse:
    settings = get_settings()
    path = model or str(settings.model_path)

    df = get_data_source().fetch_recent(symbol.upper(), days=days, interval="1m")
    df = add_all_features(df)
    df = build_targets(df)

    try:
        metrics = evaluate_model(df, path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ModelMetricsResponse(model_path=str(path), metrics=metrics)
