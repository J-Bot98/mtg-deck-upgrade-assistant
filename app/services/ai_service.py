"""
AI-powered card recommendation service.

Takes real card data from the database and uses an LLM to analyze
which cards are relevant for a specific Commander deck strategy.
"""

import logging
from typing import Optional, List, Dict

from sqlalchemy import select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_client import LLMClient
from app.clients.scryfall_client import ScryfallClient
from app.models.card_model import MTGCard

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Magic: The Gathering Commander deck builder.

IMPORTANT RULES:
- You can ONLY recommend cards from the list provided by the user.
- Do NOT invent or hallucinate card names. Every card you mention MUST be from the provided list.
- You have deep knowledge of MTG mechanics, synergies, and Commander strategy.
- When recommending cards, explain WHY each card fits the deck strategy.
- Group recommendations by priority: must-have, strong picks, worth considering.
- Consider mana curve, color requirements, and card synergies.
- Be conversational and helpful. If the user hasn't specified enough, ask clarifying questions.
- Respond in the same language the user writes in.
"""

SEARCH_PROMPT = """You are an MTG deck-building assistant. Given a user's question about a Commander deck, output ONLY a JSON object with search keywords to find relevant cards.

Output format (JSON only, no explanation):
{"keywords": ["keyword1", "keyword2", ...], "types": ["type1", ...]}

- keywords: oracle text terms to search (mechanics, effects, words that appear on relevant cards)
- types: card types to prioritize (creature, instant, sorcery, enchantment, artifact, etc.)

Examples:
- Winota → keywords: ["human", "non-human", "attack", "token"], types: ["creature"]
- Mill → keywords: ["mill", "library", "graveyard", "self-mill"], types: ["instant", "sorcery", "creature"]
- Keep it to 6-8 keywords max."""


class AIService:
    """Service for AI-powered card recommendations."""

    _commander_cache: dict = {}  # class-level cache, persists for server lifetime

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def chat(
        self,
        message: str,
        set_codes: Optional[List[str]] = None,
        set_code: Optional[str] = None,  # legacy
        commander: Optional[str] = None,
        strategy: Optional[str] = None,
        provider: str = "groq",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,        visible_cards: Optional[List[str]] = None,    ) -> str:
        all_set_codes = list(set_codes or [])
        if set_code and set_code not in all_set_codes:
            all_set_codes.append(set_code)
        all_set_codes = [s.lower() for s in all_set_codes]

        logger.info("── AI CHAT ──────────────────────────────")
        logger.info("  message   : %s", message[:80])
        logger.info("  set_codes : %s", all_set_codes)
        logger.info("  commander : %s", commander)

        client = LLMClient(provider=provider, api_key=api_key, model=model)
        context_parts = []

        if commander:
            context_parts.append(f"Commander: {commander}")
            # Fetch real commander data from Scryfall
            commander_data = await self._lookup_commander(commander)
            if commander_data:
                context_parts.append(commander_data)
                logger.info("  [step 0] commander data fetched from Scryfall")
            else:
                logger.info("  [step 0] commander not found on Scryfall")
        if strategy:
            context_parts.append(f"Deck strategy: {strategy}")

        if all_set_codes:
            context_parts.append(f"Selected sets: {', '.join(s.upper() for s in all_set_codes)}")

        # If the user is viewing specific cards, use those directly (skip DB search)
        if visible_cards:
            logger.info("  [context] using %d visible cards from UI", len(visible_cards))
            context_parts.append(
                f"\n--- CARDS CURRENTLY VISIBLE IN USER'S GRID ---\n"
                + "\n".join(f"• {name}" for name in visible_cards)
                + "\n--- END OF CARD LIST ---"
            )
        elif all_set_codes:
            logger.info("  [step 1] extracting search criteria from message...")
            search_keywords, search_types = await self._get_search_criteria(
                message, commander, strategy, client
            )
            logger.info("  [step 1] keywords=%s  types=%s", search_keywords, search_types)

            # Step 2: fetch relevant cards; fall back to top-by-rarity if nothing matches
            for sc in all_set_codes:
                logger.info("  [step 2] querying DB for set=%s with keywords...", sc)
                cards = await self._get_cards_for_context(
                    sc, commander, search_keywords, search_types
                )
                if not cards and (search_keywords or search_types):
                    logger.info("  [step 2] no keyword matches, falling back to top cards for %s", sc)
                    cards = await self._get_cards_for_context(sc, commander)
                logger.info("  [step 2] found %d cards for %s", len(cards), sc)
                if cards:
                    cards_text = self._format_cards_for_llm(cards)
                    context_parts.append(
                        f"\n--- AVAILABLE CARDS FROM SET '{sc.upper()}' ---\n"
                        f"{cards_text}\n"
                        f"--- END OF CARD LIST ---"
                    )
                else:
                    context_parts.append(f"\nNote: no cards synced yet for set {sc.upper()}.")

        full_message = ("\n".join(context_parts) + "\n\n") if context_parts else ""
        full_message += f"User message: {message}"

        logger.info("  [step 3] calling LLM (context ~%d chars)...", len(full_message))
        messages = list(conversation_history or [])
        messages.append({"role": "user", "content": full_message})

        try:
            response = await client.chat(
                user_message=full_message,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=3000,
            )
            logger.info("  [step 3] LLM response: %d chars", len(response))
            logger.info("────────────────────────────────────────")
            return response
        except Exception as e:
            logger.error("AI chat error: %s", e)
            return f"Error communicating with {provider}: {str(e)}"

    async def _lookup_commander(self, name: str) -> Optional[str]:
        """Fetch commander card data from Scryfall, cached in memory."""
        cache_key = name.lower().strip()
        if cache_key in self._commander_cache:
            logger.info("  [step 0] commander '%s' served from cache", name)
            return self._commander_cache[cache_key]
        try:
            async with ScryfallClient() as client:
                results = await client.search_cards(f'!\'{name}\'')
            if not results:
                self._commander_cache[cache_key] = None
                return None
            c = results[0]
            lines = ["Commander card data (from Scryfall):"]
            lines.append(f"  Name: {c.get('name')}")
            lines.append(f"  Mana cost: {c.get('mana_cost', '')}")
            lines.append(f"  Type: {c.get('type_line', '')}")
            lines.append(f"  Oracle text: {c.get('oracle_text', '')}")
            if c.get('power'):
                lines.append(f"  P/T: {c['power']}/{c['toughness']}")
            lines.append(f"  Color identity: {c.get('color_identity', [])}")
            result = "\n".join(lines)
            self._commander_cache[cache_key] = result
            logger.info("  [step 0] commander '%s' fetched and cached", name)
            return result
        except Exception as e:
            logger.warning("Commander lookup failed for '%s': %s", name, e)
            return None

    async def _get_search_criteria(
        self,
        message: str,
        commander: Optional[str],
        strategy: Optional[str],
        client: "LLMClient",
    ) -> tuple:
        """Step 1: ask the AI what to search for, returns (keywords, types)."""
        import json
        context = f"Commander: {commander or 'unknown'}\nStrategy: {strategy or 'unknown'}\nQuestion: {message}"
        try:
            raw = await client.chat(
                user_message=context,
                system_prompt=SEARCH_PROMPT,
                temperature=0.2,
                max_tokens=200,
            )
            # Extract JSON from response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end]) if start >= 0 else {}
            return data.get("keywords", []), data.get("types", [])
        except Exception as e:
            logger.warning("Search criteria extraction failed: %s", e)
            return [], []

    async def _get_cards_for_context(
        self,
        set_code: str,
        commander: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
    ) -> List[MTGCard]:
        """Fetch cards filtered by search keywords to keep context small."""
        from sqlalchemy import func

        sub = (
            select(func.min(MTGCard.id).label("min_id"))
            .where(MTGCard.set_code == set_code.lower())
            .group_by(MTGCard.name)
            .subquery()
        )
        query = (
            select(MTGCard)
            .where(MTGCard.id.in_(select(sub.c.min_id)))
            .where(~MTGCard.type_line.ilike("%basic land%"))
        )

        # Filter by oracle text keywords (OR logic) if provided
        if keywords:
            kw_filters = [
                or_(
                    MTGCard.oracle_text.ilike(f"%{kw}%"),
                    MTGCard.name.ilike(f"%{kw}%"),
                    MTGCard.type_line.ilike(f"%{kw}%"),
                )
                for kw in keywords
            ]
            query = query.where(or_(*kw_filters))

        # Also filter by card type if provided
        if types:
            type_filters = [MTGCard.type_line.ilike(f"%{t}%") for t in types]
            query = query.where(or_(*type_filters))

        query = query.order_by(MTGCard.rarity.desc(), MTGCard.name).limit(30)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _format_cards_for_llm(cards: List[MTGCard]) -> str:
        """Format cards into a compact text representation for the LLM context."""
        lines = []
        for card in cards:
            parts = [f"• {card.name}"]

            if card.mana_cost:
                parts.append(f"({card.mana_cost})")

            if card.type_line:
                parts.append(f"- {card.type_line}")

            if card.power and card.toughness:
                parts.append(f"[{card.power}/{card.toughness}]")

            if card.oracle_text:
                text = card.oracle_text.replace("\n", " ")
                if len(text) > 80:
                    text = text[:80] + "..."
                parts.append(f"| {text}")

            if card.rarity:
                parts.append(f"({card.rarity})")

            lines.append(" ".join(parts))

        return "\n".join(lines)