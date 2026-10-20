from fastapi import FastAPI

from app.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="PG Rent Tracker API", version="0.1.0")
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    return app


app = create_app()
