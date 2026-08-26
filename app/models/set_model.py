"""
SQLAlchemy ORM model for Magic: The Gathering sets.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class MTGSet(Base):
    """Represents a Magic: The Gathering card set."""

    __tablename__ = "sets"

    # --- Primary key ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Scryfall identifiers ---
    scryfall_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)

    # --- Set metadata ---
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    released_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    set_type: Mapped[str] = mapped_column(String(50), nullable=False, default="expansion", index=True)
    card_count: Mapped[int] = mapped_column(Integer, default=0)
    digital: Mapped[bool] = mapped_column(Boolean, default=False)
    nonfoil_only: Mapped[bool] = mapped_column(Boolean, default=False)
    foil_only: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- URIs ---
    icon_svg_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scryfall_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MTGSet(code='{self.code}', name='{self.name}')>"