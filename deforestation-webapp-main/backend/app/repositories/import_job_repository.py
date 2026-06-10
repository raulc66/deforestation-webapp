"""ImportJob repository."""
from app.models.import_job import ImportJob
from .base import BaseRepository


class ImportJobRepository(BaseRepository[ImportJob]):
    collection_name = "import_jobs"
    model = ImportJob

    async def list_recent(self, limit: int = 20) -> list[ImportJob]:
        return await self.find_many({}, limit=limit, sort=[("created_at", -1)])
