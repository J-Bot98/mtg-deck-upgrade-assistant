"""Test: sync sets from Scryfall into the local database."""

import asyncio
from app.database.session import async_session_factory, init_db
from app.services.sync_service import SyncService

async def test():
    # Initialize database tables
    await init_db()

    # Sync sets
    async with async_session_factory() as session:
        service = SyncService(session)
        result = await service.sync_sets()

        print("Sync result:")
        for key, value in result.items():
            print(f"  {key}: {value}")

asyncio.run(test())