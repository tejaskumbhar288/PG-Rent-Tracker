"""Password hashing and JWT access tokens.

Argon2 for hashing and HS256 JWTs for sessions (CLAUDE.md §5). Tokens carry
nothing but the owner's id, so no owner data leaks into a value stored on a
phone.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()

# A valid argon2 hash of a value no owner can have. Login verifies against this
# when no account matches the identifier, so "no such account" costs the same as
# "wrong password" and the two cannot be told apart by timing.
DUMMY_HASH: str = _hasher.hash("owner-does-not-exist")


class TokenError(Exception):
    """An access token could not be decoded into an owner id."""


def hash_password(plain: str) -> str:
    """Return an argon2 hash of ``plain``, safe to store."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return whether ``plain`` matches ``hashed``. Never raises."""
    try:
        return _hasher.verify(hashed, plain)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(owner_id: uuid.UUID, *, now: datetime | None = None) -> str:
    """Sign an access token for ``owner_id``.

    ``now`` exists so tests can mint an already-expired token without a clock
    library; production always uses the current UTC time.
    """
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(owner_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    """Return the owner id a token was issued for.

    Raises:
        TokenError: the token is malformed, expired, signed with another key, or
            carries a subject that is not a UUID.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("could not decode access token") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise TokenError("access token has no subject")
    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise TokenError("access token subject is not a uuid") from exc
