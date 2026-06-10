"""Base document model with ObjectId<->str coercion and datetime helpers."""
from datetime import datetime, timezone
from typing import Annotated, Any
from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _coerce_objectid(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        return v
    raise TypeError(f"Cannot coerce {type(v)} to ObjectId string")


PyObjectId = Annotated[str, BeforeValidator(_coerce_objectid)]


def utcnow() -> datetime:
    """Timezone-aware current UTC datetime - the single source of `now` truth."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Coerce a datetime to a timezone-aware UTC value."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId | None = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: dict | None):
        if doc is None:
            return None
        return cls.model_validate(doc)

    def to_mongo(self) -> dict:
        # mode="python" preserves datetime objects (Mongo stores them natively).
        data = self.model_dump(by_alias=True, exclude_none=True, mode="python")
        if "_id" in data and isinstance(data["_id"], str) and ObjectId.is_valid(data["_id"]):
            data["_id"] = ObjectId(data["_id"])
        return data
