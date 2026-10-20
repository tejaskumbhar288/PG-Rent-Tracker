from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        503: {
            "description": "Database unavailable",
            "content": {"application/json": {"example": {"detail": "database unavailable"}}},
        }
    },
)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    """Liveness + DB connectivity check.

    Returns 200 ``{"status": "ok"}`` when the database answers, otherwise
    503 ``{"detail": "database unavailable"}``.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — any DB failure means unhealthy
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return HealthResponse(status="ok")
