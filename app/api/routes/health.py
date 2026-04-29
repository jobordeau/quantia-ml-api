from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.api.schemas import HealthResponse
from app.config import get_settings
from app.models.predictor import get_predictor

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    predictor = get_predictor()
    return HealthResponse(
        status="ok",
        utc=datetime.now(UTC),
        model_loaded=predictor.is_loaded,
        data_source=settings.data_source,
        version=__version__,
    )
