"""
API endpoints for Commander deck analysis via EDHREC + local DB + Scryfall enrichment.
"""
import logging
import asyncio
import httpx
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_db
from app.clients.archidekt_client import EDHRECClient
from app.models.card_model import MTGCard

logger = logging.getLogger(__name__)
router = APIRouter()

SCRYFALL_COLLECTION_URL = "https://api.scryfall.com/cards/collection"


async def _scryfall_batch_lookup(names: list[str]) -> dict:
    """Batch-fetch card data from Scryfall (up to 75 per request)."""
    result = {}
    async with httpx.AsyncClient(timeout=20) as client:
        for i in range(0, len(names), 75):
            batch = names[i:i+75]
            payload = {"identifiers": [{"name": n} for n in batch]}
            resp = await client.post(SCRYFALL_COLLECTION_URL, json=payload,
                                     headers={"User-Agent": "MTG-Deck-Upgrade-Assistant/2.0"})
            if resp.status_code == 200:
                for card in resp.json().get("data", []):
                    result[card["name"]] = card
            await asyncio.sleep(0.1)  # respect Scryfall rate limit
    return result


@router.get("/commander")
async def analyze_commander(
    name: str = Query(..., description="Commander card name"),
    limit: int = Query(700, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Fetch EDHREC stats + enrich with local DB and Scryfall card data."""
    client = EDHRECClient()
    try:
        data = await client.get_commander_cards(name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Commander '{name}' not found on EDHREC.")

    edhrec_cards = data["cards"][:limit]
    card_names = [c["name"] for c in edhrec_cards]

    # Step 1: local DB lookup
    result = await db.execute(select(MTGCard).where(MTGCard.name.in_(card_names)))
    db_cards = {c.name: c for c in result.scalars().all()}

    # Step 2: Scryfall batch lookup for cards not in local DB
    missing = [n for n in card_names if n not in db_cards]
    logger.info("EDHREC enrichment: %d in DB, %d fetching from Scryfall", len(db_cards), len(missing))
    scryfall_cards = {}
    if missing:
        scryfall_cards = await _scryfall_batch_lookup(missing)

    enriched = []
    for card in edhrec_cards:
        db_card = db_cards.get(card["name"])
        sf_card = scryfall_cards.get(card["name"]) if not db_card else None
        pct = round(card["decks"] / max(card["potential_decks"], 1) * 100)

        # Prefer local DB, fall back to Scryfall
        type_line = (db_card.type_line if db_card else None) or (sf_card.get("type_line") if sf_card else None)
        color_identity = (db_card.color_identity if db_card else None) or (sf_card.get("color_identity") if sf_card else [])
        oracle_text = (db_card.oracle_text if db_card else None) or (sf_card.get("oracle_text") if sf_card else None)
        scryfall_uri = (db_card.scryfall_uri if db_card else None) or (sf_card.get("scryfall_uri") if sf_card else None)

        # Get image URL from local DB or Scryfall batch response (avoids frontend rate limits)
        image_uris = (db_card.image_uris if db_card else None)
        if not image_uris and sf_card:
            image_uris = sf_card.get("image_uris") or (
                sf_card.get("card_faces", [{}])[0].get("image_uris")
            )

        enriched.append({
            "name": card["name"],
            "decks": card["decks"],
            "pct": pct,
            "synergy": card["synergy"],
            "image_uris": image_uris,
            "type_line": type_line,
            "color_identity": color_identity or [],
            "oracle_text": oracle_text,
            "scryfall_uri": scryfall_uri,
        })

    return {
        "commander": data["commander"],
        "num_decks": data["num_decks"],
        "cards": enriched,
    }
