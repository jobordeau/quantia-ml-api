from fastapi import APIRouter

from app.api.routes import data, health, model, pattern, prediction, trade

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(data.router)
api_router.include_router(prediction.router)
api_router.include_router(pattern.router)
api_router.include_router(trade.router)
api_router.include_router(model.router)
