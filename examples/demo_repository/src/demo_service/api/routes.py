"""HTTP routes."""

from fastapi import APIRouter, FastAPI

from demo_service.services.users import UserService
from . import helpers


def create_app() -> FastAPI:
    application = FastAPI(title="Demo Service")
    router = APIRouter()
    service = UserService()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/users/{user_id}")
    async def get_user(user_id: int) -> dict[str, object]:
        user = await service.get_user(user_id)
        return helpers.serialize_user(user)

    application.include_router(router)
    return application
