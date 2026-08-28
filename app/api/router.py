"""
Main API router — aggregates all sub-routers.
"""

from fastapi import APIRouter

from app.api.sets import router as sets_router
from app.api.cards import router as cards_router
from app.api.sync import router as sync_router
from app.api.ai import router as ai_router
from app.api.decks import router as decks_router

api_router = APIRouter(prefix="/api")

api_router.include_router(sets_router, prefix="/sets", tags=["Sets"])
api_router.include_router(cards_router, prefix="/cards", tags=["Cards"])
api_router.include_router(sync_router, prefix="/sync", tags=["Sync"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI"])
api_router.include_router(decks_router, prefix="/decks", tags=["Decks"])