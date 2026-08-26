"""
API endpoints for MTG Sets.
"""

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.set_model import MTGSet

router = APIRouter()

@router.get("")
async def list_sets(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    released_after: Optional[str] = Query(None, description="Filter: released after date (YYYY-MM-DD)"),
    released_before: Optional[str] = Query(None, description="Filter: released before date (YYYY-MM-DD)"),
    set_type: Optional[str] = Query(None, description="Filter by set type (e.g. expansion, commander)"),
    db: AsyncSession = Depends(get_db),
):
    """List all sets with optional filters and pagination."""
    query = select(MTGSet)

    if released_after:
        query = query.where(MTGSet.released_at >= date.fromisoformat(released_after))
    if released_before:
        query = query.where(MTGSet.released_at <= date.fromisoformat(released_before))
    if set_type:
        query = query.where(MTGSet.set_type == set_type)

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch page
    query = query.order_by(MTGSet.released_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    sets = result.scalars().all()

    return {
        "data": [_set_to_dict(s) for s in sets],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.get("/recent")
async def get_recent_sets(
    limit: int = Query(5, ge=1, le=50),
    set_type: Optional[str] = Query(None, description="Filter by set type"),
    physical_only: bool = Query(True, description="Exclude digital-only sets"),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recently released sets."""
    query = select(MTGSet).where(MTGSet.released_at.isnot(None))

    if physical_only:
        query = query.where(MTGSet.digital == False)
    if set_type:
        query = query.where(MTGSet.set_type == set_type)

    query = query.order_by(MTGSet.released_at.desc()).limit(limit)
    result = await db.execute(query)
    sets = result.scalars().all()

    return [_set_to_dict(s) for s in sets]

@router.get("/{set_code}")
async def get_set(
    set_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single set by its code."""
    result = await db.execute(select(MTGSet).where(MTGSet.code == set_code))
    mtg_set = result.scalar_one_or_none()

    if mtg_set is None:
        raise HTTPException(status_code=404, detail=f"Set '{set_code}' not found.")

    return _set_to_dict(mtg_set)

def _set_to_dict(s: MTGSet) -> dict:
    """Convert a set ORM object to a dict for the API response."""
    return {
        "id": s.id,
        "scryfall_id": s.scryfall_id,
        "code": s.code,
        "name": s.name,
        "released_at": s.released_at.isoformat() if s.released_at else None,
        "set_type": s.set_type,
        "card_count": s.card_count,
        "digital": s.digital,
        "icon_svg_uri": s.icon_svg_uri,
        "scryfall_uri": s.scryfall_uri,
    }