"""Black-box API tests for specs/F2-pg-profile.md (PG profile).

Everything here talks to the running app over HTTP. Nothing imports from the
application. The only non-HTTP access is read-only/destructive-on-test-rows
SQL through psycopg, used for the three criteria the API deliberately does not
expose: ``updated_at`` (AC-15), "owner has no PG row" (AC-14) and the database
check constraint (AC-22).
"""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from conftest import (
    API,
    JWT_ALGORITHM,
    JWT_SECRET,
    bearer,
    new_owner,
    psycopg_dsn,
)

jwt = pytest.importorskip("jwt")

PG_PATH = f"{API}/pg"

PG_READ_KEYS = {"id", "name", "address", "default_rent_due_day", "created_at"}

psycopg = pytest.importorskip("psycopg")
DSN = psycopg_dsn()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def get_pg(client, token=None):
    headers = bearer(token) if token else None
    return client.get(PG_PATH, headers=headers)


def patch_pg(client, body, token=None):
    headers = bearer(token) if token else None
    return client.patch(PG_PATH, json=body, headers=headers)


def db_row(owner_id: str) -> dict:
    """Read the owner's PG row straight from Postgres."""
    assert DSN, "backend/.env has no DATABASE_URL; cannot run DB-backed checks"
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, owner_id, name, address, default_rent_due_day,"
                " created_at, updated_at FROM pgs WHERE owner_id = %s"
                " ORDER BY created_at, id",
                (owner_id,),
            )
            cols = [c.name for c in cur.description]
            rows = cur.fetchall()
    assert rows, f"no pgs row for owner {owner_id}"
    return dict(zip(cols, rows[0]))


def delete_pgs(owner_id: str) -> int:
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pgs WHERE owner_id = %s", (owner_id,))
            return cur.rowcount


# ---------------------------------------------------------------------------
# AC-1 — GET returns the signup defaults
# ---------------------------------------------------------------------------


def test_get_pg_returns_signup_defaults(client, owner):
    """Spec F2 AC-1: GET /pg returns the PG auto-created at signup."""
    _payload, token, _owner_json = owner
    r = get_pg(client, token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "My PG"
    assert body["address"] is None
    assert body["default_rent_due_day"] == 5
    uuid.UUID(body["id"])  # raises if not a UUID
    assert set(body) == PG_READ_KEYS, f"unexpected keys: {set(body) ^ PG_READ_KEYS}"


def test_get_pg_created_at_is_ist(client, owner):
    """Spec F2 §7: created_at is rendered in IST (CLAUDE.md §7 timezone rule)."""
    _p, token, _o = owner
    body = get_pg(client, token).json()
    assert body["created_at"].endswith("+05:30"), body["created_at"]


# ---------------------------------------------------------------------------
# AC-11 — authentication
# ---------------------------------------------------------------------------


def test_get_pg_without_token(client):
    """Spec F2 AC-11: GET /pg with no Authorization header is 401."""
    r = client.get(PG_PATH)
    assert r.status_code == 401
    assert r.json()["detail"] == "not authenticated"


@pytest.mark.parametrize("header", ["Bearer garbage", "Basic abc", "garbage", "Bearer"])
def test_get_pg_with_malformed_token(client, header):
    """Spec F2 AC-11: a malformed / non-bearer Authorization header is 401."""
    r = client.get(PG_PATH, headers={"Authorization": header})
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "not authenticated"


def test_update_pg_without_token(client, owner):
    """Spec F2 AC-11: PATCH /pg without a token is 401 and changes nothing."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = client.patch(PG_PATH, json={"name": "Hacked PG", "default_rent_due_day": 20})
    assert r.status_code == 401
    assert r.json()["detail"] == "not authenticated"
    assert get_pg(client, token).json() == before


def _forge(sub, secret=None, lifetime=timedelta(days=1)):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(sub),
            "iat": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
        },
        secret or JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def test_get_pg_with_expired_token(client, owner):
    """Spec F2 §7 (error table): an expired token is 401 on GET /pg."""
    _p, _token, owner_json = owner
    expired = _forge(owner_json["id"], lifetime=timedelta(minutes=-5))
    r = client.get(PG_PATH, headers=bearer(expired))
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "not authenticated"


def test_get_pg_with_foreign_signed_token(client, owner):
    """Spec F2 §7 (error table): a token signed with another secret is 401."""
    _p, _token, owner_json = owner
    forged = _forge(owner_json["id"], secret="a-totally-different-secret-value-0001")
    r = client.get(PG_PATH, headers=bearer(forged))
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "not authenticated"


def test_get_pg_with_unknown_owner_token(client):
    """Spec F2 §7 (error table): a valid token whose owner row is gone is 401.

    Not 404 — authentication is decided before the PG lookup.
    """
    token = _forge(uuid.uuid4())
    r = client.get(PG_PATH, headers=bearer(token))
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "not authenticated"


def test_patch_pg_with_expired_token(client, owner):
    """Spec F2 §7 (error table): an expired token is 401 on PATCH and changes nothing."""
    _p, token, owner_json = owner
    before = get_pg(client, token).json()
    expired = _forge(owner_json["id"], lifetime=timedelta(minutes=-5))
    r = client.patch(PG_PATH, json={"name": "Expired PG"}, headers=bearer(expired))
    assert r.status_code == 401, r.text
    assert get_pg(client, token).json() == before


@pytest.mark.parametrize("header", ["Bearer garbage", "Basic abc"])
def test_update_pg_with_malformed_token(client, owner, header):
    """Spec F2 AC-11: PATCH with a malformed token is 401 and changes nothing."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = client.patch(
        PG_PATH, json={"name": "Hacked PG"}, headers={"Authorization": header}
    )
    assert r.status_code == 401, r.text
    assert get_pg(client, token).json() == before


# ---------------------------------------------------------------------------
# AC-2 / AC-3 — update and partial update
# ---------------------------------------------------------------------------


def test_update_pg_all_fields(client, owner):
    """Spec F2 AC-2: PATCH all three fields returns 200 and persists."""
    _p, token, _o = owner
    body = {
        "name": "Sri Sai PG",
        "address": "12, 4th Cross, Koramangala, Bengaluru 560034",
        "default_rent_due_day": 10,
    }
    r = patch_pg(client, body, token)
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched["name"] == "Sri Sai PG"
    assert patched["address"] == "12, 4th Cross, Koramangala, Bengaluru 560034"
    assert patched["default_rent_due_day"] == 10
    assert set(patched) == PG_READ_KEYS

    fetched = get_pg(client, token).json()
    assert fetched == patched


def test_update_pg_partial_leaves_other_fields(client, owner):
    """Spec F2 AC-3: a PATCH with one field leaves the others untouched."""
    _p, token, _o = owner
    patch_pg(
        client,
        {"name": "Old Name", "address": "Old Address", "default_rent_due_day": 7},
        token,
    )
    before = get_pg(client, token).json()

    r = patch_pg(client, {"name": "Sri Sai PG"}, token)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["name"] == "Sri Sai PG"
    assert after["address"] == before["address"]
    assert after["default_rent_due_day"] == before["default_rent_due_day"]


# ---------------------------------------------------------------------------
# AC-4 — clearing the address
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cleared", [None, "", "   ", "\t\n "])
def test_update_pg_clears_address(client, owner, cleared):
    """Spec F2 AC-4: null / blank / whitespace address is stored as NULL."""
    _p, token, owner_json = owner
    patch_pg(client, {"address": "12, 4th Cross"}, token)
    assert get_pg(client, token).json()["address"] == "12, 4th Cross"

    r = patch_pg(client, {"address": cleared}, token)
    assert r.status_code == 200, r.text
    assert r.json()["address"] is None
    assert get_pg(client, token).json()["address"] is None
    assert db_row(owner_json["id"])["address"] is None


def test_update_pg_trims_address(client, owner):
    """Spec F2 §7 (PgUpdate table): address is trimmed before being stored."""
    _p, token, _o = owner
    r = patch_pg(client, {"address": "  12, 4th Cross  "}, token)
    assert r.status_code == 200, r.text
    assert r.json()["address"] == "12, 4th Cross"


# ---------------------------------------------------------------------------
# AC-5 / AC-6 — name rules
# ---------------------------------------------------------------------------


def test_update_pg_trims_name(client, owner):
    """Spec F2 AC-5: '  Sri Sai PG  ' is stored and returned trimmed."""
    _p, token, owner_json = owner
    r = patch_pg(client, {"name": "  Sri Sai PG  "}, token)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Sri Sai PG"
    assert get_pg(client, token).json()["name"] == "Sri Sai PG"
    assert db_row(owner_json["id"])["name"] == "Sri Sai PG"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", None, "x" * 121],
    ids=["empty", "whitespace", "null", "121-chars"],
)
def test_update_pg_rejects_bad_name(client, owner, bad):
    """Spec F2 AC-6: blank / whitespace / null / over-long name is 422, row unchanged."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = patch_pg(client, {"name": bad}, token)
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    assert get_pg(client, token).json() == before


@pytest.mark.parametrize("name", ["x" * 120, "  " + "y" * 120 + "  ", "A"])
def test_update_pg_accepts_boundary_names(client, owner, name):
    """Spec F2 §6 rule 5: 1-120 characters *after trimming* is accepted."""
    _p, token, _o = owner
    r = patch_pg(client, {"name": name}, token)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json()["name"] == name.strip()


# ---------------------------------------------------------------------------
# AC-7 — address length cap
# ---------------------------------------------------------------------------


def test_update_pg_rejects_long_address(client, owner):
    """Spec F2 AC-7: an address over 500 characters is 422, row unchanged."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = patch_pg(client, {"address": "a" * 501}, token)
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    assert get_pg(client, token).json() == before


def test_update_pg_accepts_500_char_address(client, owner):
    """Spec F2 §12 Q5: exactly 500 characters is the accepted boundary."""
    _p, token, _o = owner
    r = patch_pg(client, {"address": "a" * 500}, token)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json()["address"] == "a" * 500


# ---------------------------------------------------------------------------
# AC-8 / AC-9 — default_rent_due_day
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("day", [0, 29, -1, 100, 31])
def test_update_pg_rejects_due_day_out_of_range(client, owner, day):
    """Spec F2 AC-8: a due day outside 1-28 is 422 and changes nothing."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = patch_pg(client, {"default_rent_due_day": day}, token)
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    assert get_pg(client, token).json() == before


@pytest.mark.parametrize(
    "day",
    ["abc", 5.5, None, True, False, "", [], {}],
    ids=["abc", "5.5", "null", "true", "false", "empty-str", "list", "dict"],
)
def test_update_pg_rejects_non_integer_due_day(client, owner, day):
    """Spec F2 AC-8: a non-integer due day is 422 and changes nothing.

    ``True``/``False`` matter because Pydantic's lax mode would otherwise read
    them as 1 and 0 (spec §11).
    """
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = patch_pg(client, {"default_rent_due_day": day}, token)
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    assert get_pg(client, token).json() == before


@pytest.mark.xfail(
    reason=(
        "Spec issue: AC-8 says a due day that is 'not an integer' must be 422, "
        "but §8 step 3 prescribes a plain Annotated[int, Field(ge=1, le=28)], "
        "whose Pydantic lax mode coerces the JSON strings '7' / ' 8 ' and the "
        "integral float 9.0. Observed: 200, value stored. Harmless (the stored "
        "value is still a valid 1-28 integer and the app always sends a number) "
        "but the two sections of the spec disagree."
    ),
    strict=True,
)
@pytest.mark.parametrize("day", ["7", " 8 ", 9.0], ids=["str-7", "padded-str-8", "9.0"])
def test_update_pg_rejects_coercible_due_day(client, owner, day):
    """Spec F2 AC-8 (strict reading): a JSON value that is not an integer is 422."""
    _p, token, _o = owner
    r = patch_pg(client, {"default_rent_due_day": day}, token)
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


@pytest.mark.parametrize("day", [1, 28])
def test_update_pg_accepts_boundary_due_days(client, owner, day):
    """Spec F2 AC-9: 1 and 28 are accepted and stored."""
    _p, token, owner_json = owner
    r = patch_pg(client, {"default_rent_due_day": day}, token)
    assert r.status_code == 200, r.text
    assert r.json()["default_rent_due_day"] == day
    assert get_pg(client, token).json()["default_rent_due_day"] == day
    assert db_row(owner_json["id"])["default_rent_due_day"] == day


# ---------------------------------------------------------------------------
# AC-10 — empty body no-op
# ---------------------------------------------------------------------------


def test_update_pg_empty_body_is_noop(client, owner):
    """Spec F2 AC-10 (§12 Q7): PATCH {} is a 200 no-op returning the PG."""
    _p, token, _o = owner
    patch_pg(client, {"name": "Sri Sai PG", "address": "12, 4th Cross"}, token)
    before = get_pg(client, token).json()

    r = patch_pg(client, {}, token)
    assert r.status_code == 200, r.text
    assert r.json() == before
    assert get_pg(client, token).json() == before


# ---------------------------------------------------------------------------
# AC-12 — isolation between owners
# ---------------------------------------------------------------------------


def test_pg_isolation_between_owners(client):
    """Spec F2 AC-12: owner A's PATCH never touches owner B's PG."""
    _pa, token_a, _oa = new_owner(client)
    _pb, token_b, _ob = new_owner(client)

    r = patch_pg(
        client,
        {"name": "A's PG", "address": "A's address", "default_rent_due_day": 20},
        token_a,
    )
    assert r.status_code == 200, r.text

    a = get_pg(client, token_a).json()
    b = get_pg(client, token_b).json()

    assert a["name"] == "A's PG"
    assert a["default_rent_due_day"] == 20
    assert b["name"] == "My PG"
    assert b["address"] is None
    assert b["default_rent_due_day"] == 5
    assert a["id"] != b["id"]


def test_pg_patch_cannot_target_another_owner_via_body(client):
    """Spec F2 §6 rule 2: the PG comes from the token; body ids are ignored."""
    _pa, token_a, _oa = new_owner(client)
    _pb, token_b, _ob = new_owner(client)
    b_before = get_pg(client, token_b).json()

    r = patch_pg(
        client,
        {"name": "Injected", "id": b_before["id"], "pg_id": b_before["id"]},
        token_a,
    )
    # Either the extra keys are ignored (200) or rejected (422); what must not
    # happen is B's PG changing.
    assert r.status_code in (200, 422), r.text
    assert get_pg(client, token_b).json() == b_before


# ---------------------------------------------------------------------------
# AC-13 — response shape, id / created_at stability
# ---------------------------------------------------------------------------


def test_pg_response_omits_owner_id(client, owner):
    """Spec F2 AC-13: neither GET nor PATCH leaks owner_id or updated_at."""
    _p, token, _o = owner
    for body in (
        get_pg(client, token).json(),
        patch_pg(client, {"name": "Sri Sai PG"}, token).json(),
    ):
        assert "owner_id" not in body
        assert "updated_at" not in body
        assert set(body) == PG_READ_KEYS


def test_update_pg_keeps_id_and_created_at(client, owner):
    """Spec F2 AC-13: a PATCH leaves id and created_at unchanged."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    after = patch_pg(
        client, {"name": "Sri Sai PG", "default_rent_due_day": 12}, token
    ).json()
    assert after["id"] == before["id"]
    assert after["created_at"] == before["created_at"]


# ---------------------------------------------------------------------------
# AC-14 — owner with no PG row
# ---------------------------------------------------------------------------


def test_pg_routes_404_when_owner_has_no_pg(client):
    """Spec F2 AC-14: with no PG row both routes return 404 'pg not found'."""
    _p, token, owner_json = new_owner(client)
    assert delete_pgs(owner_json["id"]) == 1

    r_get = get_pg(client, token)
    assert r_get.status_code == 404, r_get.text
    assert r_get.json()["detail"] == "pg not found"

    r_patch = patch_pg(client, {"name": "Sri Sai PG"}, token)
    assert r_patch.status_code == 404, r_patch.text
    assert r_patch.json()["detail"] == "pg not found"

    # and nothing was auto-created (§6 rule 4)
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pgs WHERE owner_id = %s", (owner_json["id"],)
            )
            assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# AC-15 — updated_at
# ---------------------------------------------------------------------------


def test_update_pg_bumps_updated_at(client, owner):
    """Spec F2 AC-15: a successful PATCH advances updated_at past created_at."""
    _p, token, owner_json = owner
    before = db_row(owner_json["id"])
    r = patch_pg(client, {"name": "Sri Sai PG"}, token)
    assert r.status_code == 200, r.text
    after = db_row(owner_json["id"])
    assert after["updated_at"] > before["updated_at"], (
        before["updated_at"],
        after["updated_at"],
    )
    assert after["updated_at"] > after["created_at"]


# ---------------------------------------------------------------------------
# AC-22 — the database check constraint is still the backstop
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("day", [0, 29])
def test_pgs_due_day_check_constraint(client, owner, day):
    """Spec F2 AC-22: the DB rejects a due day outside 1-28 regardless of the API."""
    _p, _token, owner_json = owner
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO pgs (id, owner_id, name, address,"
                    " default_rent_due_day, created_at, updated_at)"
                    " VALUES (%s, %s, %s, NULL, %s, now(), now())",
                    (str(uuid.uuid4()), owner_json["id"], "Bad Day PG", day),
                )


# ---------------------------------------------------------------------------
# Contract checks against /openapi.json
# ---------------------------------------------------------------------------


def test_update_pg_rejects_malformed_json(client, owner):
    """Spec F2 §7: a body that is not JSON is a 422, not a 500."""
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = client.patch(
        PG_PATH,
        content=b"not json",
        headers={**bearer(token), "Content-Type": "application/json"},
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    assert get_pg(client, token).json() == before


def test_update_pg_ignores_unknown_fields(client, owner):
    """Spec F2 §7: a body with fields outside PgUpdate must not change the PG.

    The spec does not say whether unknown keys are ignored or rejected (open
    question in the report); either answer is fine as long as nothing writable
    leaks through.
    """
    _p, token, _o = owner
    before = get_pg(client, token).json()
    r = patch_pg(client, {"owner_id": str(uuid.uuid4()), "updated_at": "x"}, token)
    assert r.status_code in (200, 422), r.text
    after = get_pg(client, token).json()
    assert after == before


def test_openapi_documents_both_pg_routes(client):
    """Spec F2 §7: GET and PATCH /api/v1/pg exist with the documented statuses."""
    spec = client.get("/openapi.json").json()
    assert "/api/v1/pg" in spec["paths"], sorted(spec["paths"])
    ops = spec["paths"]["/api/v1/pg"]
    assert set(ops) == {"get", "patch"}, sorted(ops)
    assert {"200", "401", "404"} <= set(ops["get"]["responses"])
    assert {"200", "401", "404", "422"} <= set(ops["patch"]["responses"])
    assert "post" not in ops and "delete" not in ops  # §3 out of scope


def test_pg_route_answers_without_redirect(client, owner):
    """Spec F2 §8 step 5: /api/v1/pg answers directly, no trailing-slash redirect."""
    _p, token, _o = owner
    with httpx.Client(
        base_url=str(client.base_url), timeout=10.0, follow_redirects=False
    ) as c:
        r = c.get(PG_PATH, headers=bearer(token))
    assert r.status_code == 200, f"{r.status_code} -> {r.headers.get('location')}"
