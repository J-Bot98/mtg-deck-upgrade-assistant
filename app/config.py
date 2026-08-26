"""
Application configuration via environment variables.
Uses pydantic-settings to load from .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "MTG Deck Upgrade Assistant"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # --- Database (SQLite) ---
    database_url: str = "sqlite+aiosqlite:///./data/mtg.db"

    # --- Scryfall API ---
    scryfall_api_base_url: str = "https://api.scryfall.com"
    scryfall_user_agent: str = "MTGDeckUpgradeAssistant/1.0"

    # Rate limiting (milliseconds between requests)
    scryfall_search_delay_ms: int = 550
    scryfall_default_delay_ms: int = 110
    scryfall_max_retries: int = 3
    scryfall_timeout_seconds: int = 30

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000

@lru_cache
def get_settings() -> Settings:
    """Get cached application settings (singleton)."""
    return Settings()