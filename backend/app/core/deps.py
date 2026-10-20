"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.owner import Owner
from app.services.auth import get_owner_by_id

# auto_error=False so this module raises every 401 itself, with the same
# lowercase detail the rest of the API uses. Note HTTPBearer does not check the
# scheme — it hands over credentials for "Basic ..." just the same — so that
# check belongs here too.
_bearer = HTTPBearer(auto_error=False)


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_owner(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Owner:
    """Resolve the owner a bearer token was issued for.

    Raises 401 when the header is missing or not Bearer, when the token is
    malformed, expired or signed with another key, and when the owner it names
    no longer exists.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()

    try:
        owner_id = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthenticated() from exc

    owner = get_owner_by_id(db, owner_id)
    if owner is None:
        raise _unauthenticated()
    return owner


# Every owner-scoped route depends on this; F2 builds get_current_pg on top.
CurrentOwner = Annotated[Owner, Depends(get_current_owner)]
