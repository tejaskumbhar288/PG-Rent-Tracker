from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.owner import OwnerRead
from app.services.phone import normalize_phone


class SignupRequest(BaseModel):
    """New owner account. Phone and email are normalised before validation."""

    name: Annotated[str, Field(min_length=1, max_length=120)]
    phone: str
    email: EmailStr | None = None
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone", mode="before")
    @classmethod
    def _to_e164(cls, value: object) -> object:
        # A ValueError here surfaces as a 422 with the field named.
        return normalize_phone(value) if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def _blank_is_absent(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() or None
        return value


class LoginRequest(BaseModel):
    """Phone (in any accepted format) or email, plus the password.

    Deliberately permissive: a malformed identifier or a too-short password must
    come back as a generic 401, not a 422 that reveals the shape of real
    accounts.
    """

    identifier: Annotated[str, Field(min_length=1)]
    password: Annotated[str, Field(min_length=1)]


class AuthResponse(BaseModel):
    """Issued by signup and login. Includes the owner to save a round trip."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    owner: OwnerRead
