"""
Client for the EDHREC public JSON API.
Returns aggregated card statistics for Commander decks.
"""
import asyncio
import logging
import re
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://json.edhrec.com/pages"
HEADERS = {"User-Agent": "MTG-Deck-Upgrade-Assistant/2.0"}


def _to_slug(name: str) -> str:
    """Convert card name to EDHREC URL slug."""
    name = name.lower()
    name = re.sub(r"[',.]", "", name)
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


EDHREC_THEMES = [
    "budget", "expensive",
    "tribal", "token", "combo", "spellslinger", "voltron",
    "stax", "control", "aggro", "midrange", "goodstuff",
    "sacrifice", "reanimator", "graveyard", "ramp", "artifact",
    "enchantment", "lands", "counters", "draw",
]


class EDHRECClient:
    async def get_commander_cards(self, commander_name: str) -> dict:
        """
        Fetch and aggregate card stats from EDHREC main page + all available theme pages.
        Concurrently fetches all variants; skips 404s silently.
        For partner pairs, separate names with '+': 'Malcolm + Kediss'
        """
        parts = [p.strip() for p in commander_name.split('+')]
        slug = '/'.join(_to_slug(p) for p in parts)

        base_url = f"{BASE_URL}/commanders/{slug}"
        urls = [f"{base_url}.json"] + [f"{base_url}/{t}.json" for t in EDHREC_THEMES]

        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            responses = await asyncio.gather(
                *[client.get(url) for url in urls],
                return_exceptions=True
            )

        num_decks = 0
        all_cards: dict = {}
        fetched_pages = 0

        for resp in responses:
            if isinstance(resp, Exception) or resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            fetched_pages += 1

            container = data.get("container", {})
            json_dict = container.get("json_dict", {})
            commander_card = json_dict.get("card", {})
            nd = commander_card.get("num_decks", 0) or commander_card.get("numDecks", 0)
            if nd > num_decks:
                num_decks = nd

            for group in json_dict.get("cardlists", []):
                if not isinstance(group, dict):
                    continue
                for entry in group.get("cardviews", []):
                    name = entry.get("name", "")
                    if not name:
                        continue
                    existing = all_cards.get(name)
                    if not existing or entry.get("num_decks", 0) > existing.get("num_decks", 0):
                        all_cards[name] = entry

        if not all_cards:
            raise ValueError(f"No data found for commander '{commander_name}'")

        cards = [
            {
                "name": e.get("name", ""),
                "decks": e.get("num_decks", 0),
                "potential_decks": e.get("potential_decks", num_decks or 1),
                "synergy": round(e.get("synergy", 0) * 100, 1),
            }
            for e in all_cards.values()
        ]
        cards.sort(key=lambda c: c["decks"], reverse=True)
        logger.info("EDHREC: %d unique cards from %d/%d pages fetched", len(cards), fetched_pages, len(urls))
        return {"commander": commander_name, "num_decks": num_decks, "cards": cards}
