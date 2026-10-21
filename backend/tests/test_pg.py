import uuid
from collections.abc import Callable
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.pg import Pg
from tests.conftest import PG_PATH, RegisteredOwner

OTHER_PHONE = "9123456780"
ADDRESS = "12, 4th Cross, Koramangala, Bengaluru 560034"
PG_FIELDS = {"id", "name", "address", "default_rent_due_day", "created_at"}

OwnerFactory = Callable[..., RegisteredOwner]


def _pg_row(db: Session) -> Pg:
    """The single PG row, read fresh from the database."""
    db.expire_all()
    pg = db.scalar(select(Pg))
    assert pg is not None
    return pg


# --- GET /pg -----------------------------------------------------------------


def test_get_pg_returns_signup_defaults(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    response = client.get(PG_PATH, headers=registered.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "My PG"
    assert body["address"] is None
    assert body["default_rent_due_day"] == 5
    uuid.UUID(body["id"])
    datetime.fromisoformat(body["created_at"])


def test_get_pg_without_token(client: TestClient) -> None:
    response = client.get(PG_PATH)

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


@pytest.mark.parametrize("header", ["Bearer garbage", "Basic abc", "Bearer "])
def test_get_pg_with_malformed_token(
    client: TestClient, owner_factory: OwnerFactory, header: str
) -> None:
    owner_factory()

    response = client.get(PG_PATH, headers={"Authorization": header})

    assert response.status_code == 401


# --- PATCH /pg: the happy paths ----------------------------------------------


def test_update_pg_all_fields(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    response = client.patch(
        PG_PATH,
        headers=registered.headers,
        json={"name": "Sri Sai PG", "address": ADDRESS, "default_rent_due_day": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sri Sai PG"
    assert body["address"] == ADDRESS
    assert body["default_rent_due_day"] == 10
    # A second request proves it was stored, not just echoed back.
    assert client.get(PG_PATH, headers=registered.headers).json() == body


def test_update_pg_partial_leaves_other_fields(
    client: TestClient, owner_factory: OwnerFactory
) -> None:
    registered = owner_factory()
    client.patch(
        PG_PATH,
        headers=registered.headers,
        json={"address": ADDRESS, "default_rent_due_day": 12},
    )

    response = client.patch(PG_PATH, headers=registered.headers, json={"name": "Sri Sai PG"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sri Sai PG"
    assert body["address"] == ADDRESS
    assert body["default_rent_due_day"] == 12


@pytest.mark.parametrize("cleared", [None, "", "   "])
def test_update_pg_clears_address(
    client: TestClient, db: Session, owner_factory: OwnerFactory, cleared: str | None
) -> None:
    registered = owner_factory()
    client.patch(PG_PATH, headers=registered.headers, json={"address": ADDRESS})

    response = client.patch(PG_PATH, headers=registered.headers, json={"address": cleared})

    assert response.status_code == 200
    assert response.json()["address"] is None
    assert _pg_row(db).address is None


def test_update_pg_trims_name(client: TestClient, db: Session, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    response = client.patch(PG_PATH, headers=registered.headers, json={"name": "  Sri Sai PG  "})

    assert response.status_code == 200
    assert response.json()["name"] == "Sri Sai PG"
    assert _pg_row(db).name == "Sri Sai PG"


@pytest.mark.parametrize("due_day", [1, 28])
def test_update_pg_accepts_boundary_due_days(
    client: TestClient, db: Session, owner_factory: OwnerFactory, due_day: int
) -> None:
    registered = owner_factory()

    response = client.patch(
        PG_PATH, headers=registered.headers, json={"default_rent_due_day": due_day}
    )

    assert response.status_code == 200
    assert response.json()["default_rent_due_day"] == due_day
    assert _pg_row(db).default_rent_due_day == due_day


def test_update_pg_empty_body_is_noop(
    client: TestClient, db: Session, owner_factory: OwnerFactory
) -> None:
    registered = owner_factory()
    before = client.get(PG_PATH, headers=registered.headers).json()
    updated_at_before = _pg_row(db).updated_at

    response = client.patch(PG_PATH, headers=registered.headers, json={})

    assert response.status_code == 200
    assert response.json() == before
    # Nothing was written at all, so the row's updated_at has not moved either.
    assert _pg_row(db).updated_at == updated_at_before


def test_update_pg_bumps_updated_at(
    client: TestClient, db: Session, owner_factory: OwnerFactory
) -> None:
    registered = owner_factory()
    row = _pg_row(db)
    created_at, updated_at_before = row.created_at, row.updated_at

    response = client.patch(PG_PATH, headers=registered.headers, json={"name": "Sri Sai PG"})

    assert response.status_code == 200
    updated_at_after = _pg_row(db).updated_at
    assert updated_at_after > updated_at_before
    assert updated_at_after > created_at


# --- PATCH /pg: validation ---------------------------------------------------


@pytest.mark.parametrize("bad_name", ["", "   ", None, "x" * 121])
def test_update_pg_rejects_bad_name(
    client: TestClient, db: Session, owner_factory: OwnerFactory, bad_name: str | None
) -> None:
    registered = owner_factory()

    response = client.patch(PG_PATH, headers=registered.headers, json={"name": bad_name})

    assert response.status_code == 422
    assert _pg_row(db).name == "My PG"


def test_update_pg_rejects_long_address(
    client: TestClient, db: Session, owner_factory: OwnerFactory
) -> None:
    registered = owner_factory()

    response = client.patch(PG_PATH, headers=registered.headers, json={"address": "x" * 501})

    assert response.status_code == 422
    assert _pg_row(db).address is None


@pytest.mark.parametrize("due_day", [0, 29, -1, 100])
def test_update_pg_rejects_due_day_out_of_range(
    client: TestClient, db: Session, owner_factory: OwnerFactory, due_day: int
) -> None:
    registered = owner_factory()

    response = client.patch(
        PG_PATH, headers=registered.headers, json={"default_rent_due_day": due_day}
    )

    assert response.status_code == 422
    assert _pg_row(db).default_rent_due_day == 5


@pytest.mark.parametrize("due_day", ["abc", 5.5, None, True])
def test_update_pg_rejects_non_integer_due_day(
    client: TestClient, db: Session, owner_factory: OwnerFactory, due_day: object
) -> None:
    registered = owner_factory()

    response = client.patch(
        PG_PATH, headers=registered.headers, json={"default_rent_due_day": due_day}
    )

    # `true` is the interesting one: isinstance(True, int) is True, so without
    # an explicit guard Pydantic would read it as day 1.
    assert response.status_code == 422
    assert _pg_row(db).default_rent_due_day == 5


def test_update_pg_without_token(
    client: TestClient, db: Session, owner_factory: OwnerFactory
) -> None:
    owner_factory()

    response = client.patch(PG_PATH, json={"name": "Sri Sai PG"})

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}
    assert _pg_row(db).name == "My PG"


# --- scoping and shape -------------------------------------------------------


def test_pg_isolation_between_owners(client: TestClient, owner_factory: OwnerFactory) -> None:
    owner_a = owner_factory()
    owner_b = owner_factory(phone=OTHER_PHONE, name="Another Owner")

    client.patch(
        PG_PATH,
        headers=owner_a.headers,
        json={"name": "Sri Sai PG", "address": ADDRESS, "default_rent_due_day": 10},
    )

    pg_a = client.get(PG_PATH, headers=owner_a.headers).json()
    pg_b = client.get(PG_PATH, headers=owner_b.headers).json()
    assert pg_a["name"] == "Sri Sai PG"
    assert pg_a["default_rent_due_day"] == 10
    # Owner B's PG is untouched by anything owner A did.
    assert pg_b["name"] == "My PG"
    assert pg_b["address"] is None
    assert pg_b["default_rent_due_day"] == 5
    assert pg_a["id"] != pg_b["id"]


def test_pg_response_omits_owner_id(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()

    get_body = client.get(PG_PATH, headers=registered.headers).json()
    patch_body = client.patch(
        PG_PATH, headers=registered.headers, json={"name": "Sri Sai PG"}
    ).json()

    for body in (get_body, patch_body):
        assert set(body) == PG_FIELDS


def test_update_pg_keeps_id_and_created_at(client: TestClient, owner_factory: OwnerFactory) -> None:
    registered = owner_factory()
    before = client.get(PG_PATH, headers=registered.headers).json()

    after = client.patch(PG_PATH, headers=registered.headers, json={"name": "Sri Sai PG"}).json()

    assert after["id"] == before["id"]
    assert after["created_at"] == before["created_at"]


def test_pg_routes_404_when_owner_has_no_pg(
    client: TestClient, db: Session, owner_factory: OwnerFactory
) -> None:
    registered = owner_factory()
    db.execute(delete(Pg))
    db.commit()

    responses = [
        client.get(PG_PATH, headers=registered.headers),
        client.patch(PG_PATH, headers=registered.headers, json={"name": "Sri Sai PG"}),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "pg not found"}
