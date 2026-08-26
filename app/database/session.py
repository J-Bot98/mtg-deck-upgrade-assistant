"""
Database engine and session management for async SQLite via SQLAlchemy 2.x.
"""

import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, with auto commit/rollback."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_db() -> None:
    """Create all tables if they don't exist."""
    from app.models.base import Base

    db_path = settings.database_url.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized at %s", settings.database_url)