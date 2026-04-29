from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.config import get_settings
from app.models.predictor import ModelNotFoundError, get_predictor
from app.patterns import get_pattern_detector
from app.utils import get_logger, setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger(__name__)
    log.info("Starting %s v%s (env=%s, source=%s)",
             settings.app_name, __version__, settings.environment, settings.data_source)

    try:
        get_predictor()
    except ModelNotFoundError as exc:
        log.warning("No model artefact at startup: %s", exc)
    try:
        get_pattern_detector()
    except Exception as exc:
        log.warning("Pattern detector failed to load: %s", exc)

    yield
    log.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Crypto direction-prediction service for the Quantia platform. "
            "Exposes price data, model predictions, candlestick pattern detection, "
            "and a training pipeline."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        log = get_logger("app.error")
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "detail": str(exc)},
        )

    app.include_router(api_router)
    return app


app = create_app()
