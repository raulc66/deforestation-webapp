"""DataSource domain model - registry of where ForestEvents come from."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from .base import BaseDocument, utcnow


DataSourceType = Literal["csv", "api", "satellite", "scraper", "manual"]
DataSourceStatus = Literal["active", "inactive", "error", "paused"]

DATA_SOURCE_TYPES: tuple[str, ...] = ("csv", "api", "satellite", "scraper", "manual")


class DataSource(BaseDocument):
    name: str
    type: DataSourceType
    provider: str
    status: DataSourceStatus = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DataSourceCreate(BaseModel):
    name: str
    type: DataSourceType
    provider: str
    status: DataSourceStatus = "active"


class DataSourceUpdate(BaseModel):
    name: str | None = None
    type: DataSourceType | None = None
    provider: str | None = None
    status: DataSourceStatus | None = None


class DataSourcePublic(BaseModel):
    id: str
    name: str
    type: DataSourceType
    provider: str
    status: DataSourceStatus
    created_at: datetime
    updated_at: datetime
