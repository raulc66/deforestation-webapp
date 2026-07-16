"""ForestEvent routes - /api/events/*

Route ordering: all static / non-id routes (`event-types`, `stats`, `recent`,
`range`, `nearby`, `bbox`) MUST be declared BEFORE the dynamic `/{event_id}`
route.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from app.api.deps import forest_event_service_dep, get_current_user
from app.models.enums import EVENT_TYPES
from app.models.forest_event import (
    ForestEventCreate,
    ForestEventUpdate,
    ForestEventPublic,
)
from app.models.user import UserPublic
from app.services.forest_event_service import ForestEventService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/event-types")
async def list_event_types():
    return list(EVENT_TYPES)


@router.get("/stats")
async def event_stats(
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.get_stats()


@router.get("/recent", response_model=list[ForestEventPublic])
async def list_recent_events(
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=200, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.list_recent(days=days, limit=limit)


@router.get("/range", response_model=list[ForestEventPublic])
async def list_events_in_range(
    start: datetime = Query(..., description="ISO-8601 start datetime (inclusive)"),
    end: datetime = Query(..., description="ISO-8601 end datetime (inclusive)"),
    limit: int = Query(default=500, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.list_in_range(start=start, end=end, limit=limit)


@router.get("/nearby", response_model=list[ForestEventPublic])
async def list_events_nearby(
    latitude: float = Query(..., ge=-90, le=90, description="Center latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Center longitude"),
    radius: int = Query(
        default=50_000,
        ge=1,
        le=20_000_000,
        description="Search radius in meters (default 50km, max ~20,000km)",
    ),
    limit: int = Query(default=200, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    """Events within `radius` meters of (latitude, longitude), sorted by
    distance ascending. Requires the 2dsphere index on `forest_events.location`.
    """
    return await svc.list_nearby(latitude, longitude, radius, limit)


@router.get("/bbox", response_model=list[ForestEventPublic])
async def list_events_in_bbox(
    min_lat: float = Query(..., ge=-90, le=90, description="South edge"),
    min_lng: float = Query(..., ge=-180, le=180, description="West edge"),
    max_lat: float = Query(..., ge=-90, le=90, description="North edge"),
    max_lng: float = Query(..., ge=-180, le=180, description="East edge"),
    limit: int = Query(default=500, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    """Events whose location falls inside the [min_lat, min_lng] – [max_lat, max_lng]
    bounding box. Sorted by detected_at DESC.
    """
    return await svc.list_in_bbox(min_lat, min_lng, max_lat, max_lng, limit)


@router.get("/map")
async def events_for_map(
    limit: int = Query(default=500, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    """Lightweight event projection for map visualisation.

    Returns only the fields needed to render markers — id, lat/lng, severity,
    region, source and detection date.  Reuses the existing ``list_events``
    service method to avoid duplicating query logic.
    """
    events = await svc.list_events(limit=limit)
    return {
        "events": [
            {
                "id": e.id,
                "latitude": e.latitude,
                "longitude": e.longitude,
                "severity": e.severity,
                "region": e.region,
                "detected_at": e.detected_at.isoformat() if e.detected_at else None,
                "source": e.source_name or e.source_id or "Unknown",
                "land_cover_type": e.land_cover_type or "unknown",
            }
            for e in events
        ]
    }


@router.get("", response_model=list[ForestEventPublic])
async def list_events(
    severity: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    country: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.list_events(
        severity=severity,
        event_type=event_type,
        country=country,
        status=status,
        source_id=source_id,
        limit=limit,
    )


@router.post("", response_model=ForestEventPublic, status_code=201)
async def create_event(
    payload: ForestEventCreate,
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.create_event(payload)


@router.get("/{event_id}", response_model=ForestEventPublic)
async def get_event(
    event_id: str,
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.get_event(event_id)


@router.patch("/{event_id}", response_model=ForestEventPublic)
async def update_event(
    event_id: str,
    payload: ForestEventUpdate,
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    return await svc.update_event(event_id, payload)


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    _: UserPublic = Depends(get_current_user),
    svc: ForestEventService = Depends(forest_event_service_dep),
):
    await svc.delete_event(event_id)
    return None
