"""
API endpoints for MTG Cards.
"""

import math
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, distinct, Text, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.card_model import MTGCard

router = APIRouter()

@router.get("")
async def list_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    set_code: Optional[List[str]] = Query(None, alias="set"),
    name: Optional[str] = Query(None),
    colors: Optional[str] = Query(None, description="Comma-separated: W,U,B,R,G,C"),
    color_identity: Optional[str] = Query(None),
    type_line: Optional[str] = Query(None, alias="type"),
    rarity: Optional[str] = Query(None),
    min_cmc: Optional[float] = Query(None),
    max_cmc: Optional[float] = Query(None),
    text: Optional[str] = Query(None, description="Search in oracle text"),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    unique: bool = Query(True, description="Show only unique card names"),
    db: AsyncSession = Depends(get_db),
):
    """List cards with filters, sorting, pagination, and deduplication."""

    # --- Build subquery for unique cards (pick lowest id per name) ---
    if unique:
        # Get the first printing of each card name in the filtered set
        sub = select(func.min(MTGCard.id).label("min_id"))
        if set_code:
            sub = sub.where(MTGCard.set_code.in_(set_code))
        sub = sub.group_by(MTGCard.name).subquery()

        query = select(MTGCard).where(MTGCard.id.in_(select(sub.c.min_id)))
    else:
        query = select(MTGCard)
        if set_code:
            query = query.where(MTGCard.set_code.in_(set_code))

    # --- Filters ---
    if name:
        query = query.where(MTGCard.name.ilike(f"%{name}%"))
    if type_line:
        query = query.where(MTGCard.type_line.ilike(f"%{type_line}%"))
    if rarity:
        query = query.where(MTGCard.rarity == rarity)
    if min_cmc is not None:
        query = query.where(MTGCard.cmc >= min_cmc)
    if max_cmc is not None:
        query = query.where(MTGCard.cmc <= max_cmc)
    if text:
        terms = [t.strip() for t in text.split(",") if t.strip()]
        query = query.where(or_(*[MTGCard.oracle_text.ilike(f"%{t}%") for t in terms]))

    # Color identity filtering (for Commander)
    # Show cards whose color_identity is WITHIN the selected colors
    if colors:
        color_list = [c.strip().upper() for c in colors.split(",")]

        include_colorless = "C" in color_list
        if "C" in color_list:
            color_list.remove("C")

        if color_list:
            # Exclude cards containing any color NOT in the selection
            all_colors = ["W", "U", "B", "R", "G"]
            excluded = [c for c in all_colors if c not in color_list]
            for exc_color in excluded:
                query = query.where(
                    ~MTGCard.color_identity.cast(String).ilike(f'%"{exc_color}"%')
                )
        elif include_colorless:
            # Only "C" selected: show only colorless cards
            query = query.where(
                or_(
                    MTGCard.color_identity.cast(String) == "[]",
                    MTGCard.color_identity.is_(None),
                )
            )

    if color_identity:
        ci_list = [c.strip().upper() for c in color_identity.split(",")]
        ci_filters = [MTGCard.color_identity.cast(Text).ilike(f'%"{c}"%') for c in ci_list]
        query = query.where(or_(*ci_filters))

    # --- Count ---
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # --- Sorting ---
    sort_columns = {
        "name": MTGCard.name,
        "cmc": MTGCard.cmc,
        "rarity": MTGCard.rarity,
        "released_at": MTGCard.released_at,
        "set_code": MTGCard.set_code,
        "type_line": MTGCard.type_line,
    }
    sort_col = sort_columns.get(sort_by, MTGCard.name)
    if sort_dir.lower() == "desc":
        sort_col = sort_col.desc()
    query = query.order_by(sort_col)

    # --- Pagination ---
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await db.execute(query)
    cards = result.scalars().all()

    total_pages = max(1, math.ceil(total / page_size))

    return {
        "data": [_card_to_dict(c) for c in cards],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

@router.get("/{card_id}")
async def get_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single card by its internal ID."""
    result = await db.execute(select(MTGCard).where(MTGCard.id == card_id))
    card = result.scalar_one_or_none()

    if card is None:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found.")

    return _card_to_dict(card, full=True)

def _card_to_dict(c: MTGCard, full: bool = False) -> dict:
    """Convert a card ORM object to a dict for the API response."""
    data = {
        "id": c.id,
        "scryfall_id": c.scryfall_id,
        "name": c.name,
        "mana_cost": c.mana_cost,
        "cmc": c.cmc,
        "type_line": c.type_line,
        "oracle_text": c.oracle_text,
        "power": c.power,
        "toughness": c.toughness,
        "colors": c.colors,
        "color_identity": c.color_identity,
        "rarity": c.rarity,
        "set_code": c.set_code,
        "set_name": c.set_name,
        "collector_number": c.collector_number,
        "image_uris": c.image_uris,
        "prices": c.prices,
        "scryfall_uri": c.scryfall_uri,
    }

    if full:
        data.update({
            "oracle_id": c.oracle_id,
            "lang": c.lang,
            "released_at": c.released_at.isoformat() if c.released_at else None,
            "layout": c.layout,
            "keywords": c.keywords,
            "legalities": c.legalities,
            "card_faces": c.card_faces,
            "uri": c.uri,
        })

    return data