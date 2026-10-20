from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentOwner
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.owner import Owner
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest
from app.schemas.owner import OwnerRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth")

# One message for every failed login: a caller must not be able to tell an
# unknown account from a wrong password.
INVALID_CREDENTIALS = "invalid phone/email or password"

_CONFLICT_RESPONSE = {
    "description": "Phone or email already registered",
    "content": {
        "application/json": {"example": {"detail": "an account with this phone already exists"}}
    },
}
_UNAUTHORIZED_LOGIN_RESPONSE = {
    "description": "Unknown identifier or wrong password",
    "content": {"application/json": {"example": {"detail": INVALID_CREDENTIALS}}},
}
_UNAUTHENTICATED_RESPONSE = {
    "description": "Missing, malformed or expired token",
    "content": {"application/json": {"example": {"detail": "not authenticated"}}},
}


def _issue_token(owner: Owner) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(owner.id),
        owner=OwnerRead.model_validate(owner),
    )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: _CONFLICT_RESPONSE},
)
def signup(payload: SignupRequest, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    """Create an owner account, its PG, and return an access token."""
    try:
        owner, _pg = auth_service.signup_owner(
            db,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            password=payload.password,
        )
    except auth_service.DuplicatePhoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an account with this phone already exists",
        ) from exc
    except auth_service.DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an account with this email already exists",
        ) from exc

    return _issue_token(owner)


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={401: _UNAUTHORIZED_LOGIN_RESPONSE},
)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    """Exchange a phone or email plus password for an access token."""
    owner = auth_service.authenticate_owner(
        db, identifier=payload.identifier, password=payload.password
    )
    if owner is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    return _issue_token(owner)


@router.get("/me", response_model=OwnerRead, responses={401: _UNAUTHENTICATED_RESPONSE})
def me(owner: CurrentOwner) -> OwnerRead:
    """The owner the request's token belongs to."""
    return OwnerRead.model_validate(owner)
