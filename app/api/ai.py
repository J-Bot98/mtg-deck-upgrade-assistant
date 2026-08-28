"""
API endpoint for AI chat / card recommendations.
"""

import logging
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.clients.llm_client import PROVIDERS
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    """Request body for the AI chat endpoint."""
    message: str
    set_codes: Optional[List[str]] = None
    set_code: Optional[str] = None  # legacy single-set support
    commander: Optional[str] = None
    strategy: Optional[str] = None
    provider: str = "groq"
    api_key: Optional[str] = None
    model: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None
    visible_cards: Optional[List[str]] = None  # card names currently shown in the grid
class ChatResponse(BaseModel):
    """Response from the AI chat endpoint."""
    response: str
    provider: str
    model: str

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Chat with the AI about card recommendations for your Commander deck."""
    service = AIService(db)

    logger.info("AI Chat → set_code=%s set_codes=%s commander=%s provider=%s",
                request.set_code, request.set_codes, request.commander, request.provider)

    # Pass all selected sets to the service
    set_codes = request.set_codes or ([request.set_code] if request.set_code else [])

    response = await service.chat(
        message=request.message,
        set_codes=set_codes,
        commander=request.commander,
        strategy=request.strategy,
        provider=request.provider,
        api_key=request.api_key,
        model=request.model,
        conversation_history=request.history,
        visible_cards=request.visible_cards,
    )

    # Determine which model was actually used
    provider_info = PROVIDERS.get(request.provider, {})
    used_model = request.model or provider_info.get("default_model", "unknown")

    return ChatResponse(
        response=response,
        provider=request.provider,
        model=used_model,
    )

@router.get("/providers")
async def get_providers():
    """Get list of supported LLM providers and their info."""
    return PROVIDERS