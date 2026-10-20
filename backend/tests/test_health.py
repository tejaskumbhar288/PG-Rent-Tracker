from collections.abc import Generator

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_content_type(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.headers["content-type"].startswith("application/json")


def test_health_db_down() -> None:
    """When the DB raises, health reports 503 rather than 500."""
    app = create_app()

    class _BadSession:
        def execute(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("db is down")

    def _bad_db() -> Generator[object, None, None]:
        yield _BadSession()

    app.dependency_overrides[get_db] = _bad_db
    with TestClient(app) as c:
        resp = c.get("/api/v1/health")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "database unavailable"}
