from fastapi import FastAPI

from app.api.routes import auth, health


def create_app() -> FastAPI:
    app = FastAPI(title="PG Rent Tracker API", version="0.1.0")
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    return app


app = create_app()
