"""CORS behaviour for the Expo web target.

The phone does not need these headers — React Native's fetch does not enforce
origins — but a browser discards any response that lacks them.
"""

from fastapi.testclient import TestClient

from app.core.config import get_settings

ALLOWED_ORIGIN = "http://localhost:8081"
FOREIGN_ORIGIN = "http://evil.example.com"


def test_allowed_origin_gets_cors_header(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_preflight_for_login_is_allowed(client: TestClient) -> None:
    """Without a preflight answer a browser never sends the login POST at all."""
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


def test_foreign_origin_gets_no_cors_header(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": FOREIGN_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


def test_default_origins_cover_the_expo_web_dev_server() -> None:
    assert ALLOWED_ORIGIN in get_settings().cors_origin_list
