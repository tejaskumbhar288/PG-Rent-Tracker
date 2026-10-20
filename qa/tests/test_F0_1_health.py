"""Black-box acceptance tests for F0.1 — Backend skeleton.

Spec: specs/F0.1-backend-skeleton.md
The only owner-visible runtime surface in this feature is GET /api/v1/health,
plus the API conventions it establishes (prefix, JSON errors, OpenAPI contract).
"""

import httpx
import pytest

from conftest import API, BASE_URL


# ---------------------------------------------------------------------------
# AC: GET /api/v1/health returns 200 with DB up (Spec §7, §11, test_health_ok)
# ---------------------------------------------------------------------------

def test_health_ok(client):
    """Spec F0.1 §7 / §11 AC: health returns 200 with DB up."""
    r = client.get(f"{API}/health")
    assert r.status_code == 200, r.text


def test_health_body_exact(client):
    """Spec F0.1 §7 / §11 AC: body is exactly {"status": "ok"}."""
    r = client.get(f"{API}/health")
    assert r.json() == {"status": "ok"}


def test_health_content_type_json(client):
    """Spec F0.1 §10 test_health_content_type: content-type is application/json."""
    r = client.get(f"{API}/health")
    ctype = r.headers.get("content-type", "")
    assert ctype.startswith("application/json"), ctype


def test_health_no_auth_required(client):
    """Spec F0.1 §7: health requires no auth header."""
    # No Authorization header is sent; must still succeed.
    r = client.get(f"{API}/health")
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# API conventions established by this feature (CLAUDE.md §8, Spec §6)
# ---------------------------------------------------------------------------

def test_prefix_is_required(client):
    """Spec F0.1 §6 rule 3: all routes live under /api/v1 — unprefixed 404s."""
    r = client.get(f"{BASE_URL}/health")
    assert r.status_code == 404, r.text


def test_unknown_route_404_detail_shape(client):
    """CLAUDE.md §8 / Spec §6 rule 5: errors use {"detail": "..."} with proper code."""
    r = client.get(f"{API}/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


def test_health_wrong_method_405(client):
    """CLAUDE.md §8: health is GET-only; other methods are rejected with 405."""
    r = client.post(f"{API}/health")
    assert r.status_code == 405, r.text


# ---------------------------------------------------------------------------
# OpenAPI contract vs spec (Spec §7, step 2 of workflow)
# ---------------------------------------------------------------------------

def test_openapi_published(client):
    """The published contract is reachable at /openapi.json."""
    r = client.get(f"{BASE_URL}/openapi.json")
    assert r.status_code == 200, r.text


def test_openapi_declares_health(client):
    """Spec §7: the health endpoint is published under /api/v1/health (GET)."""
    spec = client.get(f"{BASE_URL}/openapi.json").json()
    assert "/api/v1/health" in spec["paths"]
    assert "get" in spec["paths"]["/api/v1/health"]


def test_openapi_health_response_schema(client):
    """Spec §8.9: HealthResponse.status is literal "ok" (no raw dicts)."""
    spec = client.get(f"{BASE_URL}/openapi.json").json()
    ref = (
        spec["paths"]["/api/v1/health"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
    )
    name = ref.split("/")[-1]
    schema = spec["components"]["schemas"][name]
    status = schema["properties"]["status"]
    # Pydantic v2 Literal["ok"] serialises as const "ok".
    assert status.get("const") == "ok" or status.get("enum") == ["ok"], status


def test_only_health_endpoint_exposed(client):
    """Spec §3 Out of scope: the skeleton ships zero domain endpoints."""
    spec = client.get(f"{BASE_URL}/openapi.json").json()
    paths = set(spec["paths"].keys())
    # Allow only the health route (ignore docs/openapi which are not in paths).
    assert paths == {"/api/v1/health"}, f"unexpected endpoints: {paths}"


# ---------------------------------------------------------------------------
# Reachability of interactive docs (used by workflow / developers)
# ---------------------------------------------------------------------------

def test_docs_reachable(client):
    """FastAPI interactive docs are served (sanity for the published contract)."""
    r = client.get(f"{BASE_URL}/docs")
    assert r.status_code == 200
