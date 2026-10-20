"""F1 criteria that the API does not expose yet — verified via read-only SQL.

Spec: specs/F1-owner-signup-and-login.md

AC-2 (signup creates the PG row), AC-21 (the stored hash is argon2, never the
plaintext) and AC-23 (the `pgs` due-day CHECK constraint) have no HTTP surface
in F1: `GET /pg` arrives in F2. Rather than declare them untestable, they are
checked against the same database the running API writes to, using only
`SELECT`s plus one deliberately-failing `INSERT` inside a rolled-back
transaction (CLAUDE.md §5: browsing data and SELECTs are fine).

Nothing here imports application code; the connection string comes from
`backend/.env`, which the QA workflow is allowed to read.
"""

import uuid

import pytest

from conftest import DEFAULT_PASSWORD, new_owner, psycopg_dsn, signup_payload, unique_digits

psycopg = pytest.importorskip("psycopg")

DSN = psycopg_dsn()
pytestmark = pytest.mark.skipif(
    not DSN, reason="DATABASE_URL not found in backend/.env — DB-level checks skipped"
)


@pytest.fixture()
def conn():
    with psycopg.connect(DSN) as c:
        yield c


# ---------------------------------------------------------------------------
# AC-2 — signup creates exactly one PG, named "My PG", due day 5
# ---------------------------------------------------------------------------

def test_AC2_signup_creates_one_pg(client, conn):
    """Spec F1 §14 AC-2: signup creates exactly one PG "My PG" with due day 5."""
    _payload, _token, owner_json = new_owner(client)
    rows = conn.execute(
        "SELECT name, address, default_rent_due_day FROM pgs WHERE owner_id = %s",
        (uuid.UUID(owner_json["id"]),),
    ).fetchall()
    assert len(rows) == 1, rows
    name, address, due_day = rows[0]
    assert name == "My PG", name
    assert address is None, address
    assert due_day == 5, due_day


def test_AC2_failed_signup_creates_neither_owner_nor_pg(client, conn):
    """Spec F1 §6 rule 5: if signup fails, neither row is committed."""
    before = conn.execute("SELECT count(*) FROM pgs").fetchone()[0]
    bad = client.post(f"{client.base_url}/api/v1/auth/signup", json=signup_payload(phone="12345"))
    assert bad.status_code == 422, bad.text
    conn.commit()  # end the implicit read transaction so the next read is fresh
    after = conn.execute("SELECT count(*) FROM pgs").fetchone()[0]
    assert after == before, (before, after)


def test_AC3_duplicate_phone_creates_no_second_pg(client, conn):
    """Spec F1 §14 AC-3 / §6 rule 5: a rejected duplicate signup adds no rows."""
    payload, _token, owner_json = new_owner(client)
    conn.commit()
    before = conn.execute("SELECT count(*) FROM owners").fetchone()[0]
    r = client.post(f"{client.base_url}/api/v1/auth/signup", json=payload)
    assert r.status_code == 409, r.text
    conn.commit()
    after = conn.execute("SELECT count(*) FROM owners").fetchone()[0]
    assert after == before, (before, after)
    pgs = conn.execute(
        "SELECT count(*) FROM pgs WHERE owner_id = %s", (uuid.UUID(owner_json["id"]),)
    ).fetchone()[0]
    assert pgs == 1, pgs


# ---------------------------------------------------------------------------
# AC-6 — the stored phone is E.164
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["{d}", "0{d}", "91{d}", "+91-{a}-{b}"])
def test_AC6_phone_stored_as_e164(client, conn, fmt):
    """Spec F1 §14 AC-6: the persisted owners.phone is +91XXXXXXXXXX."""
    digits = unique_digits()
    raw = fmt.format(d=digits, a=digits[:5], b=digits[5:])
    _payload, _token, owner_json = new_owner(client, phone=raw)
    stored = conn.execute(
        "SELECT phone FROM owners WHERE id = %s", (uuid.UUID(owner_json["id"]),)
    ).fetchone()[0]
    assert stored == f"+91{digits}", stored


# ---------------------------------------------------------------------------
# AC-21 — the password is stored as an argon2 hash
# ---------------------------------------------------------------------------

def test_AC21_password_is_argon2_hashed_in_db(client, conn):
    """Spec F1 §14 AC-21: the stored hash is argon2 and never the plaintext."""
    _payload, _token, owner_json = new_owner(client, password=DEFAULT_PASSWORD)
    stored = conn.execute(
        "SELECT password_hash FROM owners WHERE id = %s", (uuid.UUID(owner_json["id"]),)
    ).fetchone()[0]
    assert stored != DEFAULT_PASSWORD
    assert DEFAULT_PASSWORD not in stored
    assert stored.startswith("$argon2"), stored[:24]


def test_AC21_same_password_two_owners_different_hashes(client, conn):
    """Spec F1 §6 rule 6: argon2 salts per row — identical passwords differ."""
    _p1, _t1, o1 = new_owner(client, password="same-password-123")
    _p2, _t2, o2 = new_owner(client, password="same-password-123")
    hashes = [
        conn.execute(
            "SELECT password_hash FROM owners WHERE id = %s", (uuid.UUID(o["id"]),)
        ).fetchone()[0]
        for o in (o1, o2)
    ]
    assert hashes[0] != hashes[1]


# ---------------------------------------------------------------------------
# AC-23 — the pgs due-day CHECK constraint
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_day", [0, 29, -1, 31])
def test_AC23_pgs_due_day_check_constraint(client, conn, bad_day):
    """Spec F1 §14 AC-23: default_rent_due_day outside 1-28 cannot be stored.

    Performed inside a transaction that is always rolled back, so the database
    is left exactly as it was.
    """
    _payload, _token, owner_json = new_owner(client)
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction(force_rollback=True):
            conn.execute(
                "INSERT INTO pgs (id, owner_id, name, default_rent_due_day,"
                " created_at, updated_at) VALUES (%s, %s, %s, %s, now(), now())",
                (uuid.uuid4(), uuid.UUID(owner_json["id"]), "QA PG", bad_day),
            )
    conn.rollback()


# ---------------------------------------------------------------------------
# AC-29 — schema shape created by the migration
# ---------------------------------------------------------------------------

def test_AC29_owners_unique_constraints_exist(conn):
    """Spec F1 §5 / §14 AC-29: owners has unique constraints on phone and email."""
    rows = conn.execute(
        "SELECT conname, contype FROM pg_constraint"
        " WHERE conrelid = 'owners'::regclass ORDER BY conname"
    ).fetchall()
    names = {name for name, _ in rows}
    assert "uq_owners_phone" in names, names
    assert "uq_owners_email" in names, names
    assert "pk_owners" in names, names


def test_AC29_pgs_constraints_exist(conn):
    """Spec F1 §5: pgs has the FK to owners (cascade) and the due-day CHECK."""
    rows = conn.execute(
        "SELECT conname, contype, confdeltype, pg_get_constraintdef(oid)"
        " FROM pg_constraint WHERE conrelid = 'pgs'::regclass"
    ).fetchall()
    by_name = {r[0]: r for r in rows}
    assert "ck_pgs_default_rent_due_day_range" in by_name, by_name.keys()
    fks = [r for r in rows if r[1] == "f"]
    assert fks, rows
    assert fks[0][2] == "c", f"FK should be ON DELETE CASCADE, got {fks[0]}"


def test_AC29_owner_columns_match_spec(conn):
    """Spec F1 §5: owners column names, nullability and types."""
    rows = conn.execute(
        "SELECT column_name, is_nullable, data_type, character_maximum_length"
        " FROM information_schema.columns WHERE table_name = 'owners'"
    ).fetchall()
    cols = {r[0]: r[1:] for r in rows}
    assert set(cols) == {
        "id",
        "name",
        "phone",
        "email",
        "password_hash",
        "created_at",
        "updated_at",
    }, set(cols)
    assert cols["email"][0] == "YES", cols["email"]
    for required in ("id", "name", "phone", "password_hash", "created_at", "updated_at"):
        assert cols[required][0] == "NO", (required, cols[required])
    assert cols["created_at"][1] == "timestamp with time zone", cols["created_at"]
    assert cols["updated_at"][1] == "timestamp with time zone", cols["updated_at"]
    assert cols["phone"][2] == 16, cols["phone"]
    assert cols["name"][2] == 120, cols["name"]


def test_AC1_id_is_uuid_v4(client, conn):
    """Spec F1 §6 rule 1: ids are uuid4 generated in Python, not a DB function."""
    _payload, _token, owner_json = new_owner(client)
    assert uuid.UUID(owner_json["id"]).version == 4, owner_json["id"]
    pg_id = conn.execute(
        "SELECT id FROM pgs WHERE owner_id = %s", (uuid.UUID(owner_json["id"]),)
    ).fetchone()[0]
    assert uuid.UUID(str(pg_id)).version == 4, pg_id
