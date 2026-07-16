"""MongoDB persistence layer for regional weather observations.

Schema (one document per region)
---------------------------------
::

    {
        "region":         str,
        "latitude":       float,
        "longitude":      float,
        "temperature":    float,   # °C
        "humidity":       float,   # %
        "wind_speed":     float,   # km/h
        "wind_direction": float,   # degrees
        "precipitation":  float,   # mm
        "weather_code":   int,     # WMO code
        "source":         str,     # "open_meteo"
        "confidence":     float,   # 0.0 = failed fetch
        "observed_at":    datetime,
        "cached_at":      datetime,
    }

The ``region`` field acts as the document key (upserted on refresh).
``cached_at`` is updated on every write and drives TTL / staleness checks.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _fmt(doc: dict) -> dict:
    """Stringify ObjectId → ``id`` and return a clean dict."""
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class WeatherCacheRepository:
    """Read/write weather observations from the ``weather_cache`` collection."""

    collection_name = "weather_cache"

    def __init__(self, db) -> None:
        self.col = db[self.collection_name]

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    async def upsert(self, observation: dict) -> dict:
        """Insert or update a single regional weather observation.

        Keyed on ``region``.  ``cached_at`` is always set to the current UTC
        time so staleness checks are accurate.

        Parameters
        ----------
        observation:
            Must contain at least ``region``.  All other fields are merged
            into any existing document.

        Returns
        -------
        dict
            The updated document (without ``_id``).
        """
        region = observation["region"]
        now = datetime.now(timezone.utc)
        doc = {**observation, "cached_at": now}
        doc.pop("_id", None)

        await self.col.update_one(
            {"region": region},
            {"$set": doc},
            upsert=True,
        )
        result = await self.col.find_one({"region": region})
        return _fmt(result) if result else doc

    async def upsert_many(self, observations: list[dict]) -> int:
        """Upsert a list of observations.  Returns count of operations."""
        for obs in observations:
            await self.upsert(obs)
        return len(observations)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    async def get_all(self) -> list[dict]:
        """Return all cached observations."""
        cursor = self.col.find({}).sort("region", 1)
        return [_fmt(doc) async for doc in cursor]

    async def get_region(self, region: str) -> dict | None:
        """Return the cached observation for one region, or None."""
        doc = await self.col.find_one({"region": region})
        return _fmt(doc) if doc else None

    async def get_all_as_dict(self) -> dict[str, dict]:
        """Return ``{region_name: observation}`` mapping."""
        docs = await self.get_all()
        return {d["region"]: d for d in docs}

    async def is_stale(self, max_age_minutes: int = 30) -> bool:
        """Return True when the cache should be refreshed.

        The cache is considered stale when:
        * The collection is empty (no data at all), OR
        * The oldest ``cached_at`` timestamp is beyond ``max_age_minutes``.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        oldest = await self.col.find_one(
            {},
            sort=[("cached_at", 1)],
        )
        if oldest is None:
            return True
        cached_at = oldest.get("cached_at")
        if cached_at is None:
            return True
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        return cached_at < cutoff

    async def cached_at(self) -> datetime | None:
        """Return the most-recent ``cached_at`` timestamp, or None."""
        newest = await self.col.find_one({}, sort=[("cached_at", -1)])
        if newest is None:
            return None
        ts = newest.get("cached_at")
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
