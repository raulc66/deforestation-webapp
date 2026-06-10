"""DataSource service - registry of ForestEvent producers."""
import logging
from app.core.errors import ConflictError, NotFoundError
from app.models.base import utcnow
from app.models.data_source import (
    DataSource,
    DataSourceCreate,
    DataSourceUpdate,
    DataSourcePublic,
)
from app.repositories.data_source_repository import DataSourceRepository

logger = logging.getLogger("forestwatch.data_sources")


def to_public(d: DataSource) -> DataSourcePublic:
    return DataSourcePublic(
        id=d.id,
        name=d.name,
        type=d.type,
        provider=d.provider,
        status=d.status,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


DEMO_SOURCES: list[dict] = [
    {"name": "GLAD-S2 Forest Loss", "type": "satellite", "provider": "UMD GLAD"},
    {"name": "Hansen Global Forest Change", "type": "csv", "provider": "UMD"},
    {"name": "MapBiomas Alerta", "type": "api", "provider": "MapBiomas"},
    {"name": "InfoAmazonia News Scraper", "type": "scraper", "provider": "InfoAmazonia"},
    {"name": "Community Field Reports", "type": "manual", "provider": "Internal"},
    {"name": "Sentinel Hub NDVI", "type": "api", "provider": "Copernicus", "status": "paused"},
]


class DataSourceService:
    def __init__(self, repo: DataSourceRepository):
        self.repo = repo

    async def list_sources(
        self, type: str | None = None, status: str | None = None
    ) -> list[DataSourcePublic]:
        q: dict = {}
        if type:
            q["type"] = type
        if status:
            q["status"] = status
        docs = await self.repo.find_many(q, limit=500, sort=[("name", 1)])
        return [to_public(d) for d in docs]

    async def get_source(self, source_id: str) -> DataSourcePublic:
        doc = await self.repo.find_by_id(source_id)
        if not doc:
            raise NotFoundError("DataSource not found")
        return to_public(doc)

    async def create_source(self, payload: DataSourceCreate) -> DataSourcePublic:
        if await self.repo.find_by_name(payload.name):
            raise ConflictError(f"DataSource '{payload.name}' already exists")
        now = utcnow()
        ds = DataSource(**payload.model_dump(), created_at=now, updated_at=now)
        ds = await self.repo.insert(ds)
        logger.info("Created DataSource %s (%s)", ds.id, ds.name)
        return to_public(ds)

    async def update_source(
        self, source_id: str, payload: DataSourceUpdate
    ) -> DataSourcePublic:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return await self.get_source(source_id)
        updates["updated_at"] = utcnow()
        ok = await self.repo.update(source_id, updates)
        if not ok:
            raise NotFoundError("DataSource not found")
        return await self.get_source(source_id)

    async def delete_source(self, source_id: str) -> None:
        ok = await self.repo.delete(source_id)
        if not ok:
            raise NotFoundError("DataSource not found")

    async def seed_demo(self) -> dict[str, str]:
        """Idempotently seed demo data sources. Returns a {name -> id} map."""
        name_to_id: dict[str, str] = {}
        for spec in DEMO_SOURCES:
            existing = await self.repo.find_by_name(spec["name"])
            if existing:
                name_to_id[spec["name"]] = existing.id
                continue
            now = utcnow()
            ds = DataSource(**spec, created_at=now, updated_at=now)
            ds = await self.repo.insert(ds)
            name_to_id[spec["name"]] = ds.id
        logger.info("Seeded %d DataSource records", len(name_to_id))
        return name_to_id
