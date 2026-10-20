"""Shared QA fixtures for black-box API tests.

These tests talk to the running app over HTTP only. Nothing here imports
from the application under test. Base URL comes from QA_BASE_URL, defaulting
to http://localhost:8000.
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("QA_BASE_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v1"


@pytest.fixture()
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


# ---------------------------------------------------------------------------
# F1 — auth helpers (added for specs/F1-owner-signup-and-login.md)
# ---------------------------------------------------------------------------

import random
import re
import uuid
from pathlib import Path

AUTH = f"{API}/auth"

#: Repo root, used only to read backend/.env (config, not application code) so
#: that expired / wrong-owner tokens can be forged for AC-19 and AC-20.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_backend_env() -> dict[str, str]:
    """Parse backend/.env (falling back to .env.example) into a dict.

    Only configuration is read here — never application source. The JWT secret
    is needed to construct the *valid-signature-but-unacceptable* tokens the
    spec requires (expired, unknown owner).
    """
    env: dict[str, str] = {}
    for name in (".env", ".env.example"):
        path = REPO_ROOT / "backend" / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env.setdefault(key.strip(), value.split("#")[0].strip())
    return env


BACKEND_ENV = _read_backend_env()
JWT_SECRET = BACKEND_ENV.get("JWT_SECRET", "change-me")
JWT_ALGORITHM = BACKEND_ENV.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(BACKEND_ENV.get("JWT_EXPIRES_MINUTES", 60 * 24 * 30))
DATABASE_URL = BACKEND_ENV.get("DATABASE_URL", "")

DEFAULT_PASSWORD = "qa-secret-123"


def unique_digits() -> str:
    """A fresh, valid 10-digit Indian mobile number (first digit 6-9)."""
    return random.choice("6789") + "".join(random.choice("0123456789") for _ in range(9))


def unique_email(tag: str = "qa") -> str:
    return f"{tag}.{uuid.uuid4().hex[:12]}@example.com"


def signup_payload(**overrides) -> dict:
    payload = {
        "name": "QA Owner",
        "phone": unique_digits(),
        "password": DEFAULT_PASSWORD,
    }
    payload.update(overrides)
    return payload


def do_signup(client, **overrides):
    """POST /auth/signup with a unique phone; returns (response, payload)."""
    payload = signup_payload(**overrides)
    r = client.post(f"{AUTH}/signup", json=payload)
    return r, payload


def new_owner(client, **overrides):
    """Create a fresh owner and return (payload, token, owner_json)."""
    r, payload = do_signup(client, **overrides)
    assert r.status_code == 201, f"signup failed: {r.status_code} {r.text}"
    body = r.json()
    return payload, body["access_token"], body["owner"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def owner(client):
    """A fresh owner with no email: (payload, token, owner_json)."""
    return new_owner(client)


@pytest.fixture()
def authed_client(client, owner):
    """httpx client that sends the fresh owner's bearer token by default."""
    _payload, token, _owner_json = owner
    client.headers.update(bearer(token))
    return client


def psycopg_dsn() -> str | None:
    """Translate the SQLAlchemy URL in backend/.env into a libpq DSN."""
    if not DATABASE_URL:
        return None
    return re.sub(r"^postgresql\+\w+://", "postgresql://", DATABASE_URL)


def raw_get(path: str, headers: dict[str, str]) -> tuple[int, str]:
    """Send a hand-built HTTP/1.1 GET so that header values httpx rejects
    (e.g. ``Authorization: "Bearer "`` with a trailing space) can still be
    exercised. Returns (status_code, body)."""
    import socket
    from urllib.parse import urlsplit

    parts = urlsplit(BASE_URL)
    host = parts.hostname or "localhost"
    port = parts.port or 80
    lines = [f"GET {path} HTTP/1.1", f"Host: {host}:{port}", "Connection: close"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    request = ("\r\n".join(lines) + "\r\n\r\n").encode()

    with socket.create_connection((host, port), timeout=10) as sock:
        sock.sendall(request)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    raw = b"".join(chunks).decode("utf-8", "replace")
    head, _, body = raw.partition("\r\n\r\n")
    status = int(head.splitlines()[0].split()[1])
    return status, body
