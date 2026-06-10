"""ForestEvent service - business logic for the canonical event domain.

All datetime values are timezone-aware UTC. Each event carries a GeoJSON
`location` (auto-synced from `latitude`/`longitude`) that is 2dsphere-indexed
in MongoDB to power /nearby and /bbox queries.
"""
import logging
import random
from datetime import datetime, timezone, timedelta
from app.core.errors import AppError, NotFoundError
from app.models.base import ensure_utc, utcnow
from app.models.forest_event import (
    ForestEvent,
    ForestEventCreate,
    ForestEventUpdate,
    ForestEventPublic,
)
from app.models.geo import GeoJSONPoint
from app.repositories.forest_event_repository import ForestEventRepository
from app.repositories.data_source_repository import DataSourceRepository

logger = logging.getLogger("forestwatch.events")


def _to_public(e: ForestEvent, source_name: str | None = None) -> ForestEventPublic:
    location = e.location or GeoJSONPoint.from_lat_lng(e.latitude, e.longitude)
    return ForestEventPublic(
        id=e.id,
        title=e.title,
        country=e.country,
        region=e.region,
        latitude=e.latitude,
        longitude=e.longitude,
        location=location,
        event_type=e.event_type,
        severity=e.severity,
        affected_area_ha=e.affected_area_ha,
        confidence=e.confidence,
        source_id=e.source_id,
        source_name=source_name,
        detected_at=e.detected_at,
        status=e.status,
        metadata=e.metadata,
    )


def _sync_location(event: ForestEvent) -> ForestEvent:
    """Ensure `location` always reflects `latitude`/`longitude`."""
    event.location = GeoJSONPoint.from_lat_lng(event.latitude, event.longitude)
    return event


class ForestEventService:
    def __init__(
        self,
        events: ForestEventRepository,
        sources: DataSourceRepository | None = None,
    ):
        self.events = events
        self.sources = sources

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    async def _resolve_source_map(self, source_ids: list[str]) -> dict[str, str]:
        if not self.sources or not source_ids:
            return {}
        unique = list({sid for sid in source_ids if sid})
        if not unique:
            return {}
        from bson import ObjectId

        oids = [ObjectId(s) for s in unique if ObjectId.is_valid(s)]
        if not oids:
            return {}
        cursor = self.sources.col.find({"_id": {"$in": oids}}, {"name": 1})
        return {str(doc["_id"]): doc.get("name", "") async for doc in cursor}

    async def _decorate(self, docs: list[ForestEvent]) -> list[ForestEventPublic]:
        name_map = await self._resolve_source_map([d.source_id for d in docs])
        return [_to_public(d, name_map.get(d.source_id)) for d in docs]

    # ---------------------------------------------------------------------
    # Queries
    # ---------------------------------------------------------------------
    async def list_events(
        self,
        severity: str | None = None,
        event_type: str | None = None,
        country: str | None = None,
        status: str | None = None,
        source_id: str | None = None,
        limit: int = 200,
    ) -> list[ForestEventPublic]:
        q: dict = {}
        if severity:
            q["severity"] = severity
        if event_type:
            q["event_type"] = event_type
        if country:
            q["country"] = country
        if status:
            q["status"] = status
        if source_id:
            q["source_id"] = source_id
        docs = await self.events.find_many(q, limit=limit, sort=[("detected_at", -1)])
        return await self._decorate(docs)

    async def list_recent(
        self, days: int = 7, limit: int = 200
    ) -> list[ForestEventPublic]:
        cutoff = utcnow() - timedelta(days=days)
        docs = await self.events.find_many(
            {"detected_at": {"$gte": cutoff}},
            limit=limit,
            sort=[("detected_at", -1)],
        )
        return await self._decorate(docs)

    async def list_in_range(
        self, start: datetime, end: datetime, limit: int = 500
    ) -> list[ForestEventPublic]:
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        if start_utc > end_utc:
            raise AppError(
                "start must be earlier than or equal to end",
                status_code=400,
                code="invalid_range",
            )
        docs = await self.events.find_many(
            {"detected_at": {"$gte": start_utc, "$lte": end_utc}},
            limit=limit,
            sort=[("detected_at", -1)],
        )
        return await self._decorate(docs)

    async def list_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int = 200,
    ) -> list[ForestEventPublic]:
        docs = await self.events.find_nearby(latitude, longitude, radius_m, limit)
        return await self._decorate(docs)

    async def list_in_bbox(
        self,
        min_lat: float,
        min_lng: float,
        max_lat: float,
        max_lng: float,
        limit: int = 500,
    ) -> list[ForestEventPublic]:
        if min_lat > max_lat or min_lng > max_lng:
            raise AppError(
                "min_lat/min_lng must be <= max_lat/max_lng",
                status_code=400,
                code="invalid_bbox",
            )
        docs = await self.events.find_in_bbox(
            min_lat, min_lng, max_lat, max_lng, limit
        )
        return await self._decorate(docs)

    async def get_event(self, event_id: str) -> ForestEventPublic:
        doc = await self.events.find_by_id(event_id)
        if not doc:
            raise NotFoundError("ForestEvent not found")
        decorated = await self._decorate([doc])
        return decorated[0]

    # ---------------------------------------------------------------------
    # Mutations
    # ---------------------------------------------------------------------
    async def create_event(self, payload: ForestEventCreate) -> ForestEventPublic:
        data = payload.model_dump()
        if not data.get("detected_at"):
            data["detected_at"] = utcnow()
        else:
            data["detected_at"] = ensure_utc(data["detected_at"])
        event = ForestEvent(**data)
        _sync_location(event)
        event = await self.events.insert(event)
        logger.info("Created ForestEvent %s (%s)", event.id, event.title)
        decorated = await self._decorate([event])
        return decorated[0]

    async def update_event(
        self, event_id: str, payload: ForestEventUpdate
    ) -> ForestEventPublic:
        existing = await self.events.find_by_id(event_id)
        if not existing:
            raise NotFoundError("ForestEvent not found")

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if "detected_at" in updates:
            updates["detected_at"] = ensure_utc(updates["detected_at"])

        # If lat or lng was updated, re-sync the GeoJSON location.
        if "latitude" in updates or "longitude" in updates:
            new_lat = updates.get("latitude", existing.latitude)
            new_lng = updates.get("longitude", existing.longitude)
            updates["location"] = GeoJSONPoint.from_lat_lng(new_lat, new_lng).model_dump()

        if not updates:
            return await self.get_event(event_id)
        ok = await self.events.update(event_id, updates)
        if not ok:
            raise NotFoundError("ForestEvent not found")
        return await self.get_event(event_id)

    async def delete_event(self, event_id: str) -> None:
        ok = await self.events.delete(event_id)
        if not ok:
            raise NotFoundError("ForestEvent not found")

    async def get_stats(self) -> dict:
        return await self.events.stats()

    # ---------------------------------------------------------------------
    # Seeding
    # ---------------------------------------------------------------------
    async def seed_demo_data(self, source_id_pool: list[str]) -> int:
        existing = await self.events.count()
        if existing > 0:
            return 0
        if not source_id_pool:
            raise RuntimeError("seed_demo_data requires a non-empty source_id_pool")

        samples = [
            ("Amazon Basin clearing detected", "Pará", "Brazil", "logging", "critical", 412.5, -3.4653, -62.2159),
            ("Selective logging activity", "Rondônia", "Brazil", "logging", "high", 188.0, -10.83, -63.34),
            ("Slash-and-burn signature", "Mato Grosso", "Brazil", "agriculture", "high", 256.3, -12.6819, -56.9211),
            ("Road expansion in protected zone", "Madre de Dios", "Peru", "road_construction", "medium", 78.4, -12.5933, -69.1893),
            ("Palm oil expansion", "Riau", "Indonesia", "agriculture", "critical", 622.1, 0.2933, 101.7068),
            ("Illegal mining footprint", "Bolívar", "Venezuela", "mining", "high", 145.6, 7.1, -64.3),
            ("Small-scale forest loss", "Ucayali", "Peru", "logging", "low", 12.8, -8.38, -74.55),
            ("Cattle ranching expansion", "Acre", "Brazil", "agriculture", "medium", 96.7, -9.0238, -70.812),
            ("Boreal forest fire scar", "Krasnoyarsk Krai", "Russia", "wildfire", "medium", 320.0, 65.0, 95.0),
            ("Logging road expansion", "Cuvette-Ouest", "Congo", "road_construction", "low", 28.5, -0.1, 15.5),
            ("Dry-season burn", "North Kivu", "DRC", "wildfire", "high", 175.2, -1.6, 29.0),
            ("Plantation conversion", "Sabah", "Malaysia", "agriculture", "critical", 510.9, 5.41, 117.31),
            ("Coastal mangrove loss", "Sundarbans", "Bangladesh", "logging", "high", 88.6, 21.95, 89.18),
            ("Subsistence clearing", "Loreto", "Peru", "agriculture", "low", 9.4, -4.0, -73.5),
            ("Mega-fire perimeter", "California", "USA", "wildfire", "critical", 1450.0, 39.5, -121.6),
            ("Eucalyptus monoculture", "Galicia", "Spain", "agriculture", "low", 22.1, 42.9, -8.0),
            ("Wildfire scar boundary", "Attica", "Greece", "wildfire", "medium", 64.3, 38.05, 23.85),
            ("Suburban encroachment", "Yunnan", "China", "urban_expansion", "low", 16.7, 25.0, 102.7),
            ("Drought-driven dieback", "Queensland", "Australia", "unknown", "medium", 132.0, -20.9, 144.6),
            ("Illegal timber harvest", "Khabarovsk Krai", "Russia", "logging", "high", 211.5, 50.6, 137.0),
        ]
        now = datetime.now(timezone.utc)
        for title, region, country, event_type, severity, area, lat, lng in samples:
            days_ago = random.randint(0, 30)
            detected = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            event = ForestEvent(
                title=title,
                region=region,
                country=country,
                event_type=event_type,
                severity=severity,
                affected_area_ha=area,
                latitude=lat,
                longitude=lng,
                source_id=random.choice(source_id_pool),
                confidence=round(random.uniform(0.62, 0.99), 2),
                detected_at=detected,
                status=random.choice(["open", "open", "open", "investigating", "resolved"]),
                metadata={"seed": True},
            )
            _sync_location(event)
            await self.events.insert(event)
        logger.info("Seeded %d ForestEvent records", len(samples))
        return len(samples)
