"""Application entry point."""

from demo_service.api.routes import create_app
from demo_service.core.config import Settings

app = create_app()


def run() -> None:
    """Console script entry."""
    import uvicorn

    settings = Settings()
    uvicorn.run("demo_service.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
