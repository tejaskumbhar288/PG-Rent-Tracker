from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="PG Rent Tracker API", version="0.1.0")

    # Named origins only, never "*", and no credentials: auth travels in the
    # Authorization header, not cookies.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    return app


app = create_app()
