"""
Synchronization service: fetches data from Scryfall and persists it locally.
"""

import logging
from datetime import date
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.scryfall_client import ScryfallClient, ScryfallAPIError
from app.models.set_model import MTGSet
from app.models.card_model import MTGCard

logger = logging.getLogger(__name__)

class SyncService:
    """Orchestrates data synchronization between Scryfall and the local database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Set sync ------------------------------------------------------------

    async def sync_sets(self) -> dict:
        """
        Fetch all sets from Scryfall and upsert them into the local database.

        Returns a summary dict with counts.
        """
        logger.info("Starting set synchronization...")

        async with ScryfallClient() as client:
            raw_sets = await client.get_sets()

        new_count = 0
        updated_count = 0
        errors = 0

        for raw_set in raw_sets:
            try:
                data = self._parse_set(raw_set)

                # Check if set already exists
                result = await self._session.execute(
                    select(MTGSet).where(MTGSet.scryfall_id == data["scryfall_id"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing record
                    for key, value in data.items():
                        if key not in ("id", "created_at"):
                            setattr(existing, key, value)
                    updated_count += 1
                else:
                    # Insert new record
                    new_set = MTGSet(**data)
                    self._session.add(new_set)
                    new_count += 1

            except Exception as e:
                errors += 1
                logger.error("Error processing set '%s': %s", raw_set.get("code", "?"), e)

        await self._session.commit()

        summary = {
            "entity": "sets",
            "total_retrieved": len(raw_sets),
            "new_records": new_count,
            "updated_records": updated_count,
            "errors": errors,
        }
        logger.info(
            "Set sync complete: %d retrieved, %d new, %d updated, %d errors",
            len(raw_sets), new_count, updated_count, errors,
        )
        return summary

    async def sync_cards_for_family(self, set_code: str) -> dict:
        """Sync cards for a set AND all its sub-sets (same parent_set_code)."""
        set_code = set_code.lower()

        # Collect all set codes in the family
        result = await self._session.execute(
            select(MTGSet.code).where(
                (MTGSet.code == set_code) |
                (
                    (MTGSet.parent_set_code == set_code) &
                    (MTGSet.digital == False) &
                    (MTGSet.set_type != 'alchemy')
                )
            )
        )
        family_codes = [row[0] for row in result.fetchall()]

        if not family_codes:
            return {"error": f"Set '{set_code}' not found. Run set sync first."}

        logger.info("Syncing family for '%s': %s", set_code, family_codes)
        results = []
        for code in family_codes:
            r = await self.sync_cards_for_set(code)
            results.append(r)

        return {
            "set_code": set_code,
            "family": family_codes,
            "total_retrieved": sum(r.get("total_retrieved", 0) for r in results),
            "new_records": sum(r.get("new_records", 0) for r in results),
            "updated_records": sum(r.get("updated_records", 0) for r in results),
            "details": results,
        }

    # -- Card sync -----------------------------------------------------------

    async def sync_cards_for_set(self, set_code: str) -> dict:
        """
        Fetch all cards for a given set from Scryfall and upsert them locally.

        Returns a summary dict with counts.
        """
        logger.info("Starting card sync for set '%s'...", set_code)

        # Verify the set exists locally
        result = await self._session.execute(
            select(MTGSet).where(MTGSet.code == set_code)
        )
        local_set = result.scalar_one_or_none()

        if local_set is None:
            logger.warning("Set '%s' not found locally. Sync sets first.", set_code)
            return {
                "entity": "cards",
                "set_code": set_code,
                "error": f"Set '{set_code}' not found. Run set sync first.",
            }

        async with ScryfallClient() as client:
            raw_cards = await client.get_cards_by_set(set_code)

        new_count = 0
        updated_count = 0
        errors = 0

        for raw_card in raw_cards:
            try:
                data = self._parse_card(raw_card)

                # Check if card already exists
                result = await self._session.execute(
                    select(MTGCard).where(MTGCard.scryfall_id == data["scryfall_id"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    for key, value in data.items():
                        if key not in ("id", "created_at"):
                            setattr(existing, key, value)
                    updated_count += 1
                else:
                    new_card = MTGCard(**data)
                    self._session.add(new_card)
                    new_count += 1

            except Exception as e:
                errors += 1
                logger.error("Error processing card '%s': %s", raw_card.get("name", "?"), e)

        await self._session.commit()

        summary = {
            "entity": "cards",
            "set_code": set_code,
            "total_retrieved": len(raw_cards),
            "new_records": new_count,
            "updated_records": updated_count,
            "errors": errors,
        }
        logger.info(
            "Card sync for '%s' complete: %d retrieved, %d new, %d updated, %d errors",
            set_code, len(raw_cards), new_count, updated_count, errors,
        )
        return summary

    # -- Parsers -------------------------------------------------------------

    @staticmethod
    def _parse_set(raw: dict) -> dict:
        """Transform a raw Scryfall set object into a dict for our ORM model."""
        released_at = raw.get("released_at")
        if released_at and isinstance(released_at, str):
            try:
                released_at = date.fromisoformat(released_at)
            except ValueError:
                released_at = None

        return {
            "scryfall_id": raw["id"],
            "code": raw["code"],
            "name": raw["name"],
            "released_at": released_at,
            "set_type": raw.get("set_type", "unknown"),
            "card_count": raw.get("card_count", 0),
            "digital": raw.get("digital", False),
            "nonfoil_only": raw.get("nonfoil_only", False),
            "foil_only": raw.get("foil_only", False),
            "icon_svg_uri": raw.get("icon_svg_uri"),
            "scryfall_uri": raw.get("scryfall_uri"),
            "search_uri": raw.get("search_uri"),
            "parent_set_code": raw.get("parent_set_code"),
        }

    @staticmethod
    def _parse_card(raw: dict) -> dict:
        """
        Transform a raw Scryfall card object into a dict for our ORM model.

        Handles multi-faced cards by falling back to card_faces[0]
        for fields missing on the top-level object.
        """
        # For multi-face cards, some fields are only on card_faces
        face = {}
        card_faces = raw.get("card_faces")
        if card_faces and isinstance(card_faces, list) and len(card_faces) > 0:
            face = card_faces[0]

        released_at = raw.get("released_at")
        if released_at and isinstance(released_at, str):
            try:
                released_at = date.fromisoformat(released_at)
            except ValueError:
                released_at = None

        return {
            "scryfall_id": raw["id"],
            "oracle_id": raw.get("oracle_id"),
            "name": raw.get("name", face.get("name", "Unknown")),
            "lang": raw.get("lang", "en"),
            "released_at": released_at,
            "layout": raw.get("layout"),
            "mana_cost": raw.get("mana_cost") or face.get("mana_cost"),
            "cmc": raw.get("cmc"),
            "type_line": raw.get("type_line") or face.get("type_line"),
            "oracle_text": raw.get("oracle_text") or face.get("oracle_text"),
            "power": raw.get("power") or face.get("power"),
            "toughness": raw.get("toughness") or face.get("toughness"),
            "colors": raw.get("colors") or face.get("colors"),
            "color_identity": raw.get("color_identity"),
            "keywords": raw.get("keywords"),
            "set_code": raw.get("set", ""),
            "set_name": raw.get("set_name"),
            "collector_number": raw.get("collector_number"),
            "rarity": raw.get("rarity"),
            "edhrec_rank": raw.get("edhrec_rank"),
            "image_uris": raw.get("image_uris") or face.get("image_uris"),
            "prices": raw.get("prices"),
            "legalities": raw.get("legalities"),
            "card_faces": card_faces,
            "scryfall_uri": raw.get("scryfall_uri"),
            "uri": raw.get("uri"),
            "raw_data": raw,  # Preserve full Scryfall response
        }