"""DataSource repository."""
from app.models.data_source import DataSource
from .base import BaseRepository


class DataSourceRepository(BaseRepository[DataSource]):
    collection_name = "data_sources"
    model = DataSource

    async def find_by_name(self, name: str) -> DataSource | None:
        return await self.find_one({"name": name})

    async def list_all(self) -> list[DataSource]:
        return await self.find_many({}, limit=500, sort=[("name", 1)])
