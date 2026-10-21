from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentPg
from app.db.session import get_db
from app.schemas.pg import PgRead, PgUpdate
from app.services import pg as pg_service

# No path parameter anywhere: the PG comes from the token, so there is nothing
# for one owner to point at another owner's PG with (CLAUDE.md §7).
router = APIRouter(prefix="/pg")

_UNAUTHENTICATED_RESPONSE = {
    "description": "Missing, malformed or expired token",
    "content": {"application/json": {"example": {"detail": "not authenticated"}}},
}
_PG_NOT_FOUND_RESPONSE = {
    "description": "The owner has no PG",
    "content": {"application/json": {"example": {"detail": "pg not found"}}},
}
_RESPONSES = {401: _UNAUTHENTICATED_RESPONSE, 404: _PG_NOT_FOUND_RESPONSE}


# The empty path keeps these on "/api/v1/pg" exactly — "/" would make FastAPI
# redirect every request to a trailing slash.
@router.get("", response_model=PgRead, responses=_RESPONSES)
def get_pg(pg: CurrentPg) -> PgRead:
    """The PG belonging to the request's owner."""
    return PgRead.model_validate(pg)


@router.patch("", response_model=PgRead, responses={**_RESPONSES, 422: {"description": "Invalid"}})
def update_pg_details(
    payload: PgUpdate,
    pg: CurrentPg,
    db: Annotated[Session, Depends(get_db)],
) -> PgRead:
    """Update the PG's name, address and/or default rent due day.

    Partial: ``exclude_unset`` means only the fields the request mentioned are
    applied, so an absent ``address`` is left alone while an explicit ``null``
    clears it. An empty body is a valid no-op.
    """
    updated = pg_service.update_pg(db, pg, payload.model_dump(exclude_unset=True))
    return PgRead.model_validate(updated)
