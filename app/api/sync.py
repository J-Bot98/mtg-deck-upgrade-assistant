"""
API endpoints for Scryfall data synchronization.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.services.sync_service import SyncService

from typing import List

router = APIRouter()

@router.post("/sets")
async def sync_sets(
    db: AsyncSession = Depends(get_db),
):
    """Sync all MTG sets from Scryfall into the local database."""
    service = SyncService(db)
    result = await service.sync_sets()
    return result

@router.post("/sets/{set_code}/cards")
async def sync_cards_for_set(
    set_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Sync all cards for a specific set from Scryfall."""
    service = SyncService(db)
    result = await service.sync_cards_for_set(set_code)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result

@router.post("/sets/{set_code}/cards/family")
async def sync_cards_for_family(
    set_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Sync cards for a set AND all its sub-sets (promos, tokens, commander decks, etc.)."""
    service = SyncService(db)
    result = await service.sync_cards_for_family(set_code)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result

@router.delete("/sets/{set_code}/cards")
async def delete_cards_for_set(
    set_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete all cached cards for a set (and its sub-sets)."""
    from sqlalchemy import delete as sql_delete
    from app.models.card_model import MTGCard
    from app.models.set_model import MTGSet
    from sqlalchemy import select

    set_code = set_code.lower()
    sub_result = await db.execute(
        select(MTGSet.code).where(MTGSet.parent_set_code == set_code)
    )
    family_codes = [set_code] + [r[0] for r in sub_result.fetchall()]

    result = await db.execute(
        sql_delete(MTGCard).where(MTGCard.set_code.in_(family_codes))
    )
    await db.commit()
    return {"deleted": result.rowcount, "sets": family_codes}

@router.post("/sets/cards/batch")
async def sync_cards_for_multiple_sets(
    set_codes: List[str],
    db: AsyncSession = Depends(get_db),
):
    """Sync cards for multiple sets at once. Send a JSON body like: ["dft", "fdn", "dsk"]"""
    service = SyncService(db)
    results = []

    for code in set_codes:
        result = await service.sync_cards_for_set(code)
        results.append(result)

    total_cards = sum(r.get("total_retrieved", 0) for r in results)
    total_new = sum(r.get("new_records", 0) for r in results)

    return {
        "sets_synced": len(set_codes),
        "total_cards_retrieved": total_cards,
        "total_new_cards": total_new,
        "details": results,
    }