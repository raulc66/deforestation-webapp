"""Base repository defining the persistence contract."""
from typing import Generic, TypeVar, Type
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from app.models.base import BaseDocument

T = TypeVar("T", bound=BaseDocument)


class BaseRepository(Generic[T]):
    collection_name: str
    model: Type[T]

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db[self.collection_name]

    async def insert(self, doc: T) -> T:
        payload = doc.to_mongo()
        payload.pop("_id", None)
        result = await self.col.insert_one(payload)
        doc.id = str(result.inserted_id)
        return doc

    async def find_by_id(self, _id: str) -> T | None:
        if not ObjectId.is_valid(_id):
            return None
        doc = await self.col.find_one({"_id": ObjectId(_id)})
        return self.model.from_mongo(doc)

    async def find_one(self, query: dict) -> T | None:
        doc = await self.col.find_one(query)
        return self.model.from_mongo(doc)

    async def find_many(self, query: dict | None = None, limit: int = 200, sort: list | None = None) -> list[T]:
        cursor = self.col.find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.limit(limit)
        return [self.model.from_mongo(d) for d in await cursor.to_list(limit)]

    async def update(self, _id: str, updates: dict) -> bool:
        if not ObjectId.is_valid(_id):
            return False
        result = await self.col.update_one({"_id": ObjectId(_id)}, {"$set": updates})
        return result.modified_count > 0

    async def delete(self, _id: str) -> bool:
        if not ObjectId.is_valid(_id):
            return False
        result = await self.col.delete_one({"_id": ObjectId(_id)})
        return result.deleted_count > 0

    async def count(self, query: dict | None = None) -> int:
        return await self.col.count_documents(query or {})
