from demo_service.services.users import UserService
from demo_service.utils.ids import normalize_id


def test_normalize_id() -> None:
    assert normalize_id("7") == 7


async def test_get_user() -> None:
    service = UserService()
    user = await service.get_user(1)
    assert user.email == "ada@example.com"
