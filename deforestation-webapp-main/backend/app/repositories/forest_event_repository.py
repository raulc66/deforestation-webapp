"""ForestEvent repository - persistence for canonical forest events."""
from app.models.forest_event import ForestEvent
from app.models.geo import bbox_polygon
from .base import BaseRepository


class ForestEventRepository(BaseRepository[ForestEvent]):
    collection_name = "forest_events"
    model = ForestEvent

    # ------------------------------------------------------------------
    # Geospatial queries (require the 2dsphere index on `location`)
    # ------------------------------------------------------------------
    async def find_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int = 200,
    ) -> list[ForestEvent]:
        """Events within `radius_m` meters of (lat, lng), sorted by distance ASC.

        `$nearSphere` does its own distance-based sorting, so we don't pass an
        explicit sort here.
        """
        query = {
            "location": {
                "$nearSphere": {
                    "$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                    "$maxDistance": radius_m,
                }
            }
        }
        cursor = self.col.find(query).limit(limit)
        return [self.model.from_mongo(d) for d in await cursor.to_list(limit)]

    async def find_in_bbox(
        self,
        min_lat: float,
        min_lng: float,
        max_lat: float,
        max_lng: float,
        limit: int = 500,
    ) -> list[ForestEvent]:
        """Events inside the [min_lat,min_lng]–[max_lat,max_lng] bounding box."""
        query = {
            "location": {
                "$geoWithin": {"$geometry": bbox_polygon(min_lat, min_lng, max_lat, max_lng)}
            }
        }
        cursor = self.col.find(query).limit(limit).sort([("detected_at", -1)])
        return [self.model.from_mongo(d) for d in await cursor.to_list(limit)]

    # ------------------------------------------------------------------
    # Stats (severity + event-type rollups)
    # ------------------------------------------------------------------
    async def stats(self) -> dict:
        sev_pipeline = [
            {"$group": {
                "_id": "$severity",
                "count": {"$sum": 1},
                "area": {"$sum": "$affected_area_ha"},
            }}
        ]
        by_severity = {
            doc["_id"]: {"count": doc["count"], "area_ha": round(doc["area"], 2)}
            async for doc in self.col.aggregate(sev_pipeline)
        }

        type_pipeline = [
            {"$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "area": {"$sum": "$affected_area_ha"},
            }}
        ]
        by_type = {
            doc["_id"]: {"count": doc["count"], "area_ha": round(doc["area"], 2)}
            async for doc in self.col.aggregate(type_pipeline)
        }

        total = await self.count()
        total_area = round(sum(s["area_ha"] for s in by_severity.values()), 2)

        return {
            "total_events": total,
            "total_alerts": total,  # back-compat
            "total_area_ha": total_area,
            "by_severity": by_severity,
            "by_event_type": by_type,
        }
