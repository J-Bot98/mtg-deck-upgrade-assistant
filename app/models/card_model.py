"""
SQLAlchemy ORM model for Magic: The Gathering cards.
"""

from datetime import date, datetime
from typing import Optional, List, Dict

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class MTGCard(Base):
    """Represents a single Magic: The Gathering card printing."""

    __tablename__ = "cards"

    # --- Primary key ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Scryfall identifiers ---
    scryfall_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    oracle_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # --- Card identity ---
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(5), default="en")
    released_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    layout: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # --- Mana & stats ---
    mana_cost: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cmc: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    type_line: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    oracle_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    power: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    toughness: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    edhrec_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # --- Colors (stored as JSON arrays) ---
    colors: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    color_identity: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    # --- Keywords ---
    keywords: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    # --- Set relationship ---
    set_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("sets.code"),
        nullable=False,
        index=True,
    )
    set_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collector_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rarity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    # --- Complex data (stored as JSON) ---
    image_uris: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    prices: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    legalities: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    card_faces: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)

    # --- URIs ---
    scryfall_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Raw data (full Scryfall response for future use) ---
    raw_data: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MTGCard(name='{self.name}', set='{self.set_code}')>"