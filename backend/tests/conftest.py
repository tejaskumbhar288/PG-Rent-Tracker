from collections.abc import Callable, Generator
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

settings = get_settings()

# Separate test database — never the dev DB. Falls back clearly if unset.
_TEST_URL = settings.test_database_url or settings.database_url
test_engine = create_engine(_TEST_URL, pool_pre_ping=True, future=True)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)

API = "/api/v1"
SIGNUP_PATH = f"{API}/auth/signup"
LOGIN_PATH = f"{API}/auth/login"
ME_PATH = f"{API}/auth/me"


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Generator[None, None, None]:
    """Create all tables once for the session, drop them at the end."""
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture(autouse=True)
def _clean_tables() -> None:
    """Empty every table before each test.

    ``_create_schema`` is session-scoped and nothing else removes rows, so
    without this the second test to sign up would collide on
    ``uq_owners_phone`` and fail for the wrong reason. Truncating on entry
    rather than on exit means it never waits on a transaction a finished test
    still holds, and it also clears rows left behind by a crashed run.
    """
    tables = list(reversed(Base.metadata.sorted_tables))
    if not tables:
        return
    targets = ", ".join(f'"{table.name}"' for table in tables)
    with test_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {targets} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class RegisteredOwner(NamedTuple):
    """An owner created through the signup endpoint, ready to make requests."""

    payload: dict[str, Any]
    token: str
    owner: dict[str, Any]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def owner_payload() -> Callable[..., dict[str, Any]]:
    """Build a valid signup body; pass keywords to override single fields."""

    def _build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "Suresh Kumar",
            "phone": "+919876543210",
            "password": "hunter2hunter2",
        }
        payload.update(overrides)
        return payload

    return _build


@pytest.fixture
def owner_factory(
    client: TestClient, owner_payload: Callable[..., dict[str, Any]]
) -> Callable[..., RegisteredOwner]:
    """Sign an owner up through the API and hand back their token and data."""

    def _create(**overrides: Any) -> RegisteredOwner:
        payload = owner_payload(**overrides)
        response = client.post(SIGNUP_PATH, json=payload)
        assert response.status_code == 201, response.text
        body = response.json()
        return RegisteredOwner(payload=payload, token=body["access_token"], owner=body["owner"])

    return _create
