"""Owner signup and authentication.

Routes stay thin (CLAUDE.md §9): everything about creating an owner, pairing
them with a PG and checking a password lives here.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.models.owner import Owner
from app.models.pg import Pg
from app.services.phone import normalize_phone

DEFAULT_PG_NAME = "My PG"
DEFAULT_RENT_DUE_DAY = 5


class DuplicatePhoneError(Exception):
    """An owner with this phone already exists."""


class DuplicateEmailError(Exception):
    """An owner with this email already exists."""


def get_owner_by_id(db: Session, owner_id: uuid.UUID) -> Owner | None:
    return db.get(Owner, owner_id)


def _owner_by_phone(db: Session, phone: str) -> Owner | None:
    return db.scalar(select(Owner).where(Owner.phone == phone))


def _owner_by_email(db: Session, email: str) -> Owner | None:
    return db.scalar(select(Owner).where(Owner.email == email))


def signup_owner(
    db: Session, *, name: str, phone: str, email: str | None, password: str
) -> tuple[Owner, Pg]:
    """Create an owner and the PG they manage, in a single transaction.

    ``phone`` must already be normalised to E.164 and ``email`` lowercased — the
    request schema does that, so the uniqueness checks here compare like with
    like.

    Raises:
        DuplicatePhoneError, DuplicateEmailError: the identifier is taken.
    """
    if _owner_by_phone(db, phone) is not None:
        raise DuplicatePhoneError
    if email is not None and _owner_by_email(db, email) is not None:
        raise DuplicateEmailError

    owner = Owner(name=name, phone=phone, email=email, password_hash=hash_password(password))
    owner.pgs.append(Pg(name=DEFAULT_PG_NAME, default_rent_due_day=DEFAULT_RENT_DUE_DAY))
    db.add(owner)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error_for(exc) from exc

    return owner, owner.pgs[0]


def _duplicate_error_for(exc: IntegrityError) -> Exception:
    """Map a unique-violation to the field that collided.

    Two signups racing past the pre-checks both reach the database and one loses;
    the violated constraint's name says which identifier was taken.
    """
    diagnostics = getattr(exc.orig, "diag", None)
    detail = getattr(diagnostics, "constraint_name", None) or str(exc.orig)
    if "email" in detail:
        return DuplicateEmailError()
    return DuplicatePhoneError()


def authenticate_owner(db: Session, *, identifier: str, password: str) -> Owner | None:
    """Return the owner matching ``identifier`` + ``password``, else ``None``.

    An identifier that is neither a valid phone nor an email is treated as a
    failed login rather than a validation error, so a caller cannot use the
    response to work out which accounts exist.
    """
    owner = _owner_by_identifier(db, identifier)
    if owner is None:
        # Spend the same time hashing as a real check would, so "no such
        # account" and "wrong password" are not distinguishable by timing.
        verify_password(password, DUMMY_HASH)
        return None
    if not verify_password(password, owner.password_hash):
        return None
    return owner


def _owner_by_identifier(db: Session, identifier: str) -> Owner | None:
    candidate = (identifier or "").strip()
    if "@" in candidate:
        return _owner_by_email(db, candidate.lower())
    try:
        phone = normalize_phone(candidate)
    except ValueError:
        return None
    return _owner_by_phone(db, phone)
