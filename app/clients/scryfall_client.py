"""
Async HTTP client for the Scryfall REST API.

Handles rate limiting, pagination, retries, and error handling.
"""

import asyncio
import logging
from typing import Any, Optional, List, Dict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class ScryfallAPIError(Exception):
    """Raised when the Scryfall API returns an error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Scryfall API error {status_code}: {message}")

class ScryfallNotFoundError(ScryfallAPIError):
    """Raised when a resource is not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(status_code=404, message=message)

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class ScryfallClient:
    """
    Async client for the Scryfall REST API.

    Usage::

        async with ScryfallClient() as client:
            sets = await client.get_sets()
            cards = await client.get_cards_by_set("fdn")
    """

    def __init__(self) -> None:
        self._base_url = settings.scryfall_api_base_url.rstrip("/")
        self._search_delay = settings.scryfall_search_delay_ms / 1000.0
        self._default_delay = settings.scryfall_default_delay_ms / 1000.0
        self._max_retries = settings.scryfall_max_retries
        self._timeout = settings.scryfall_timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None

    # -- Context manager -----------------------------------------------------

    async def __aenter__(self) -> "ScryfallClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "User-Agent": settings.scryfall_user_agent,
                "Accept": "application/json;q=0.9,*/*;q=0.8",
            },
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- Internal helpers ----------------------------------------------------

    def _get_delay(self, url: str) -> float:
        """Return the appropriate delay based on the endpoint."""
        if "/cards/search" in url or "/cards/named" in url:
            return self._search_delay  # 550ms
        return self._default_delay  # 110ms

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict:
        """
        Execute an HTTP request with rate limiting and retry logic.
        """
        if not self._client:
            raise RuntimeError("ScryfallClient must be used as an async context manager.")

        last_exception: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            # Rate limiting: wait before each request
            delay = self._get_delay(url)
            await asyncio.sleep(delay)

            try:
                response = await self._client.request(method, url, **kwargs)

                # Success
                if response.status_code == 200:
                    return response.json()

                # Rate limited — wait and retry
                if response.status_code == 429:
                    wait_time = 30 * attempt
                    logger.warning(
                        "Rate limited (attempt %d/%d). Waiting %ds...",
                        attempt, self._max_retries, wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = ScryfallAPIError(429, "Rate limit exceeded")
                    continue

                # Not found — don't retry
                if response.status_code == 404:
                    error_data = response.json() if response.content else {}
                    raise ScryfallNotFoundError(
                        message=error_data.get("details", "Resource not found")
                    )

                # Server error — retry
                if response.status_code >= 500:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Server error %d (attempt %d/%d). Retrying in %ds...",
                        response.status_code, attempt, self._max_retries, wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = ScryfallAPIError(
                        response.status_code, response.text[:200]
                    )
                    continue

                # Other client errors — don't retry
                error_data = response.json() if response.content else {}
                raise ScryfallAPIError(
                    response.status_code,
                    error_data.get("details", response.text[:200]),
                )

            except httpx.TimeoutException:
                wait_time = 2 ** attempt
                logger.warning(
                    "Timeout (attempt %d/%d). Retrying in %ds...",
                    attempt, self._max_retries, wait_time,
                )
                await asyncio.sleep(wait_time)
                last_exception = ScryfallAPIError(0, "Request timeout")

            except httpx.RequestError as exc:
                wait_time = 2 ** attempt
                logger.warning(
                    "Network error: %s (attempt %d/%d). Retrying in %ds...",
                    exc, attempt, self._max_retries, wait_time,
                )
                await asyncio.sleep(wait_time)
                last_exception = ScryfallAPIError(0, str(exc))

        # All retries exhausted
        raise ScryfallAPIError(0, f"All {self._max_retries} retries exhausted: {last_exception}")

    async def _get(self, path: str, **kwargs: Any) -> dict:
        """GET request wrapper."""
        return await self._request("GET", path, **kwargs)

    async def _paginate(self, path: str, **kwargs: Any) -> List[dict]:
        """
        Follow Scryfall pagination and collect all results.

        Scryfall returns:
        - data: list of objects
        - has_more: bool
        - next_page: full URL for next page
        """
        all_data: List[dict] = []
        url = path

        while True:
            response = await self._request("GET", url, **kwargs)
            data = response.get("data", [])
            all_data.extend(data)

            logger.info(
                "Fetched page: %d items (total so far: %d)",
                len(data), len(all_data),
            )

            if not response.get("has_more", False):
                break

            next_page = response.get("next_page")
            if not next_page:
                break

            # next_page is a full URL — use it directly
            url = next_page
            kwargs = {}  # params already embedded in next_page

        return all_data

    # -- Public API ----------------------------------------------------------

    async def get_sets(self) -> List[dict]:
        """Retrieve all MTG sets from Scryfall."""
        logger.info("Fetching all sets from Scryfall...")
        response = await self._get("/sets")
        sets = response.get("data", [])
        logger.info("Retrieved %d sets.", len(sets))
        return sets

    async def get_set(self, set_code: str) -> dict:
        """Retrieve a single set by its code."""
        logger.info("Fetching set '%s'...", set_code)
        return await self._get(f"/sets/{set_code}")

    async def get_cards_by_set(self, set_code: str) -> List[dict]:
        """
        Retrieve ALL cards belonging to a set.
        Handles pagination automatically (175 cards per page).
        """
        logger.info("Fetching cards for set '%s'...", set_code)
        cards = await self._paginate(
            "/cards/search",
            params={
                "q": f"e:{set_code}",
                "order": "set",
                "unique": "prints",
            },
        )
        logger.info("Retrieved %d cards for set '%s'.", len(cards), set_code)
        return cards

    async def search_cards(self, query: str) -> List[dict]:
        """Search cards using Scryfall full-text search syntax."""
        logger.info("Searching cards: '%s'", query)
        cards = await self._paginate(
            "/cards/search",
            params={"q": query},
        )
        logger.info("Search returned %d cards.", len(cards))
        return cards