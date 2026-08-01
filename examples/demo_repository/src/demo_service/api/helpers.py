"""Route helpers using relative imports."""

from ..models.user import User


def serialize_user(user: User) -> dict[str, object]:
    return {"id": user.id, "email": user.email, "active": user.active}
