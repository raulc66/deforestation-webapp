"""Shared geospatial primitives.

GeoJSON conforms to RFC 7946. MongoDB 2dsphere indexes require coordinates in
`[longitude, latitude]` order — the helpers here are the single source of
truth so we never get the order wrong.
"""
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class GeoJSONPoint(BaseModel):
    """GeoJSON Point — `coordinates = [longitude, latitude]` per RFC 7946."""

    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(min_length=2, max_length=2)

    @field_validator("coordinates")
    @classmethod
    def _validate_coords(cls, v: list[float]) -> list[float]:
        lng, lat = v[0], v[1]
        if not (-180.0 <= lng <= 180.0):
            raise ValueError("longitude must be in [-180, 180]")
        if not (-90.0 <= lat <= 90.0):
            raise ValueError("latitude must be in [-90, 90]")
        return v

    @classmethod
    def from_lat_lng(cls, latitude: float, longitude: float) -> "GeoJSONPoint":
        return cls(type="Point", coordinates=[longitude, latitude])

    @property
    def longitude(self) -> float:
        return self.coordinates[0]

    @property
    def latitude(self) -> float:
        return self.coordinates[1]


def bbox_polygon(min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> dict:
    """Build a GeoJSON Polygon describing the bounding box (closed ring)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_lng, min_lat],
            [max_lng, min_lat],
            [max_lng, max_lat],
            [min_lng, max_lat],
            [min_lng, min_lat],
        ]],
    }
