import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.owner import Owner
from app.models.pg import Pg
from app.services.phone import normalize_phone
from tests.conftest import LOGIN_PATH, ME_PATH, SIGNUP_PATH, RegisteredOwner

E164 = "+919876543210"
OTHER_PHONE = "9123456780"
PASSWORD = "hunter2hunter2"

OwnerPayload = Callable[..., dict[str, Any]]
OwnerFactory = Callable[..., RegisteredOwner]


# --- signup -----------------------------------------------------------------


def test_signup_success(client: TestClient, owner_payload: OwnerPayload) -> None:
    response = client.post(SIGNUP_PATH, json=owner_payload(phone="98765 43210"))

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["owner"]["name"] == "Suresh Kumar"
    assert body["owner"]["phone"] == E164
    assert body["owner"]["email"] is None
    uuid.UUID(body["owner"]["id"])
    # Parseable instant; the offset depends on the DB session timezone.
    datetime.fromisoformat(body["owner"]["created_at"])


def test_signup_creates_pg(db: Session, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    pgs = db.scalars(select(Pg).where(Pg.owner_id == uuid.UUID(registered.owner["id"]))).all()
    assert len(pgs) == 1
    assert pgs[0].name == "My PG"
    assert pgs[0].address is None
    assert pgs[0].default_rent_due_day == 5


def test_signup_duplicate_phone(
    client: TestClient, db: Session, owner_payload: OwnerPayload
) -> None:
    assert client.post(SIGNUP_PATH, json=owner_payload()).status_code == 201

    response = client.post(SIGNUP_PATH, json=owner_payload(name="Someone Else"))

    assert response.status_code == 409
    assert response.json() == {"detail": "an account with this phone already exists"}
    assert len(db.scalars(select(Owner)).all()) == 1


def test_signup_duplicate_phone_other_format(
    client: TestClient, owner_payload: OwnerPayload
) -> None:
    assert client.post(SIGNUP_PATH, json=owner_payload(phone=E164)).status_code == 201

    response = client.post(SIGNUP_PATH, json=owner_payload(phone="98765 43210"))

    assert response.status_code == 409
    assert response.json() == {"detail": "an account with this phone already exists"}


def test_signup_duplicate_email(client: TestClient, owner_payload: OwnerPayload) -> None:
    first = owner_payload(email="Suresh@Example.com")
    assert client.post(SIGNUP_PATH, json=first).status_code == 201

    response = client.post(
        SIGNUP_PATH, json=owner_payload(phone=OTHER_PHONE, email="suresh@example.com")
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "an account with this email already exists"}


@pytest.mark.parametrize(
    "raw", ["98765 43210", "09876543210", "919876543210", "+91-98765-43210", E164]
)
def test_signup_normalises_phone(
    client: TestClient, db: Session, owner_payload: OwnerPayload, raw: str
) -> None:
    response = client.post(SIGNUP_PATH, json=owner_payload(phone=raw))

    assert response.status_code == 201
    assert response.json()["owner"]["phone"] == E164
    owner = db.scalar(select(Owner))
    assert owner is not None
    assert owner.phone == E164


@pytest.mark.parametrize("raw", ["12345", "0512345678", "98765432100", "abcdefghij", ""])
def test_signup_invalid_phone(
    client: TestClient, db: Session, owner_payload: OwnerPayload, raw: str
) -> None:
    response = client.post(SIGNUP_PATH, json=owner_payload(phone=raw))

    assert response.status_code == 422
    assert db.scalars(select(Owner)).all() == []


@pytest.mark.parametrize("password", ["short", "1234567", ""])
def test_signup_short_password(
    client: TestClient, owner_payload: OwnerPayload, password: str
) -> None:
    assert client.post(SIGNUP_PATH, json=owner_payload(password=password)).status_code == 422


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_signup_blank_name(client: TestClient, owner_payload: OwnerPayload, name: str) -> None:
    assert client.post(SIGNUP_PATH, json=owner_payload(name=name)).status_code == 422


def test_signup_without_email(client: TestClient, db: Session, owner_payload: OwnerPayload) -> None:
    omitted = client.post(SIGNUP_PATH, json=owner_payload())
    blank = client.post(SIGNUP_PATH, json=owner_payload(phone=OTHER_PHONE, email=""))

    assert omitted.status_code == 201
    assert blank.status_code == 201
    assert [owner.email for owner in db.scalars(select(Owner)).all()] == [None, None]


def test_signup_hides_password_hash(client: TestClient, owner_payload: OwnerPayload) -> None:
    payload = owner_payload()

    response = client.post(SIGNUP_PATH, json=payload)

    assert "password_hash" not in response.text
    assert payload["password"] not in response.text


def test_password_is_hashed_in_db(
    client: TestClient, db: Session, owner_payload: OwnerPayload
) -> None:
    payload = owner_payload()
    client.post(SIGNUP_PATH, json=payload)

    owner = db.scalar(select(Owner))
    assert owner is not None
    assert owner.password_hash != payload["password"]
    assert owner.password_hash.startswith("$argon2")


# --- login ------------------------------------------------------------------


def test_login_with_phone(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    response = client.post(
        LOGIN_PATH, json={"identifier": registered.payload["phone"], "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["owner"]["id"] == registered.owner["id"]


def test_login_with_email(client: TestClient, owner_factory: OwnerFactory) -> None:
    owner_factory(email="suresh@example.com")

    response = client.post(
        LOGIN_PATH, json={"identifier": "Suresh@Example.COM", "password": PASSWORD}
    )

    assert response.status_code == 200


def test_login_with_unnormalised_phone(client: TestClient, owner_factory: OwnerFactory) -> None:
    owner_factory(phone=E164)

    response = client.post(LOGIN_PATH, json={"identifier": "098765 43210", "password": PASSWORD})

    assert response.status_code == 200


def test_login_wrong_password(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    response = client.post(
        LOGIN_PATH, json={"identifier": registered.payload["phone"], "password": "not-it"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid phone/email or password"}


def test_login_unknown_identifier_same_message(
    client: TestClient, owner_factory: OwnerFactory
) -> None:
    registered = owner_factory()

    wrong_password = client.post(
        LOGIN_PATH, json={"identifier": registered.payload["phone"], "password": "not-it"}
    )
    unknown_account = client.post(
        LOGIN_PATH, json={"identifier": OTHER_PHONE, "password": "not-it"}
    )

    assert unknown_account.status_code == wrong_password.status_code == 401
    assert unknown_account.json() == wrong_password.json()


@pytest.mark.parametrize("identifier", ["not-a-phone", "12345", "nobody@example.com"])
def test_login_malformed_identifier(client: TestClient, identifier: str) -> None:
    response = client.post(LOGIN_PATH, json={"identifier": identifier, "password": "whatever"})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid phone/email or password"}


# --- /auth/me ---------------------------------------------------------------


def test_me_with_token(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory(email="suresh@example.com")

    response = client.get(ME_PATH, headers=registered.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == registered.owner["id"]
    assert body["name"] == "Suresh Kumar"
    assert body["phone"] == E164
    assert body["email"] == "suresh@example.com"
    assert "password_hash" not in response.text


def test_me_without_token(client: TestClient) -> None:
    response = client.get(ME_PATH)

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


def _foreign_secret_token(owner_id: str) -> str:
    """A well-formed token signed with a key this app does not know."""
    return jwt.encode(
        {
            "sub": owner_id,
            "exp": datetime.now(UTC) + timedelta(days=1),
        },
        "a-completely-different-secret-of-sufficient-length",
        algorithm=get_settings().jwt_algorithm,
    )


def _subject_not_a_uuid_token() -> str:
    return jwt.encode(
        {"sub": "not-a-uuid", "exp": datetime.now(UTC) + timedelta(days=1)},
        get_settings().jwt_secret,
        algorithm=get_settings().jwt_algorithm,
    )


def _no_subject_token() -> str:
    return jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(days=1)},
        get_settings().jwt_secret,
        algorithm=get_settings().jwt_algorithm,
    )


@pytest.mark.parametrize(
    "kind",
    [
        "garbage",
        "empty",
        "basic-scheme",
        "no-scheme",
        "foreign-secret",
        "subject-not-uuid",
        "no-subject",
    ],
)
def test_me_with_malformed_token(
    client: TestClient, owner_factory: OwnerFactory, kind: str
) -> None:
    registered = owner_factory()
    headers = {
        "garbage": "Bearer garbage",
        "empty": "Bearer ",
        "basic-scheme": f"Basic {registered.token}",
        "no-scheme": registered.token,
        "foreign-secret": f"Bearer {_foreign_secret_token(registered.owner['id'])}",
        "subject-not-uuid": f"Bearer {_subject_not_a_uuid_token()}",
        "no-subject": f"Bearer {_no_subject_token()}",
    }[kind]

    response = client.get(ME_PATH, headers={"Authorization": headers})

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_me_with_expired_token(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()
    stale = create_access_token(
        uuid.UUID(registered.owner["id"]), now=datetime.now(UTC) - timedelta(days=31)
    )

    response = client.get(ME_PATH, headers={"Authorization": f"Bearer {stale}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_me_with_unknown_owner_token(client: TestClient) -> None:
    token = create_access_token(uuid.uuid4())

    response = client.get(ME_PATH, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_me_isolation_between_owners(client: TestClient, owner_factory: OwnerFactory) -> None:
    owner_a = owner_factory(name="Owner A", phone=E164, email="a@example.com")
    owner_b = owner_factory(name="Owner B", phone=OTHER_PHONE, email="b@example.com")

    body_a = client.get(ME_PATH, headers=owner_a.headers).json()
    body_b = client.get(ME_PATH, headers=owner_b.headers).json()

    assert body_a["id"] == owner_a.owner["id"]
    assert body_b["id"] == owner_b.owner["id"]
    assert body_a["id"] != body_b["id"]
    assert body_b["phone"] not in str(body_a)
    assert body_a["phone"] not in str(body_b)
    assert body_b["email"] not in str(body_a)


# --- schema constraints -----------------------------------------------------


@pytest.mark.parametrize("day", [0, 29, -1])
def test_pgs_due_day_check_constraint(db: Session, owner_factory: OwnerFactory, day: int) -> None:
    registered = owner_factory()

    db.add(
        Pg(
            owner_id=uuid.UUID(registered.owner["id"]),
            name="Second PG",
            default_rent_due_day=day,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --- phone normalisation (no HTTP) ------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "9876543210",
        "98765 43210",
        "09876543210",
        "919876543210",
        E164,
        "+91-98765-43210",
        "+91 (98765) 43210",
        "98765 43210",
    ],
)
def test_phone_normalisation_unit(raw: str) -> None:
    assert normalize_phone(raw) == E164


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "12345",
        "0512345678",
        "98765432100",
        "abcdefghij",
        "+91",
        "5876543210",
        "+1 234 567 8901",
    ],
)
def test_phone_normalisation_rejects(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid indian phone number"):
        normalize_phone(raw)
