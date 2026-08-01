"""User service layer."""

from demo_service.models.user import User
from demo_service.utils.ids import normalize_id


class UserService:
    """Loads users from an in-memory store."""

    def __init__(self) -> None:
        self._users = {
            1: User(id=1, email="ada@example.com", active=True),
            2: User(id=2, email="alan@example.com", active=False),
        }

    async def get_user(self, user_id: int) -> User:
        key = normalize_id(user_id)
        user = self._users.get(key)
        if user is None:
            raise KeyError(f"user {key} not found")
        return user

    def list_active(self) -> list[User]:
        return [user for user in self._users.values() if user.active]
