"""MongoDB connection management with lazy singleton."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        # tz_aware=True makes BSON datetimes return as timezone-aware UTC
        # datetime objects, which keeps sorting/filtering consistent across
        # the codebase.
        _client = AsyncIOMotorClient(get_settings().mongo_url, tz_aware=True)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[get_settings().db_name]


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
