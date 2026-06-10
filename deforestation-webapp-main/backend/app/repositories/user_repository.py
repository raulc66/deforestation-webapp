"""User repository."""
from app.models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    collection_name = "users"
    model = User

    async def find_by_email(self, email: str) -> User | None:
        return await self.find_one({"email": email.lower()})
