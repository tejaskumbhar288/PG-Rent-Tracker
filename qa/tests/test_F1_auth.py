"""Black-box acceptance tests for F1 — Owner signup and login.

Spec: specs/F1-owner-signup-and-login.md (acceptance criteria in §14).
Everything here goes over HTTP against the running API; nothing is imported
from the application. Tokens that must be valid-but-unacceptable (expired,
unknown owner) are forged with the JWT secret read from backend/.env.
"""

import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from conftest import (
    API,
    AUTH,
    DEFAULT_PASSWORD,
    JWT_ALGORITHM,
    JWT_EXPIRES_MINUTES,
    JWT_SECRET,
    bearer,
    do_signup,
    new_owner,
    raw_get,
    signup_payload,
    unique_digits,
    unique_email,
)

GENERIC_LOGIN_DETAIL = "invalid phone/email or password"
NOT_AUTHENTICATED_DETAIL = "not authenticated"
OWNER_KEYS = {"id", "name", "phone", "email", "created_at"}


def _assert_owner_shape(owner: dict) -> None:
    assert set(owner.keys()) == OWNER_KEYS, owner
    import uuid as _uuid

    _uuid.UUID(owner["id"])
    assert datetime.fromisoformat(owner["created_at"]).tzinfo is not None, owner["created_at"]


def _assert_auth_response(body: dict) -> None:
    assert set(body.keys()) == {"access_token", "token_type", "owner"}, body
    assert body["token_type"] == "bearer", body
    assert isinstance(body["access_token"], str) and body["access_token"], body
    _assert_owner_shape(body["owner"])


# ---------------------------------------------------------------------------
# AC-1 — signup returns 201 with a token and the created owner
# ---------------------------------------------------------------------------

def test_AC1_signup_success(client):
    """Spec F1 §14 AC-1: valid signup returns 201, bearer token and the owner."""
    digits = unique_digits()
    r = client.post(f"{AUTH}/signup", json=signup_payload(name="Suresh Kumar", phone=digits))
    assert r.status_code == 201, r.text
    body = r.json()
    _assert_auth_response(body)
    assert body["owner"]["name"] == "Suresh Kumar"
    assert body["owner"]["phone"] == f"+91{digits}"
    assert body["owner"]["email"] is None


def test_AC1_signup_token_is_usable_on_me(client):
    """Spec F1 §14 AC-1 + AC-16: the signup token authenticates /auth/me."""
    _payload, token, owner_json = new_owner(client)
    r = client.get(f"{AUTH}/me", headers=bearer(token))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == owner_json["id"]


def test_AC1_signup_token_claims(client):
    """Spec F1 §6 rule 9: HS256 token carries only sub/iat/exp; exp = iat + expiry."""
    _payload, token, owner_json = new_owner(client)
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert claims["sub"] == owner_json["id"], claims
    assert set(claims.keys()) == {"sub", "iat", "exp"}, claims
    assert claims["exp"] - claims["iat"] == JWT_EXPIRES_MINUTES * 60, claims
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256", header


def test_AC1_signup_trims_name(client):
    """Spec F1 §6 rule 14: name is trimmed before storage."""
    _payload, _token, owner_json = new_owner(client, name="  Suresh Kumar  ")
    assert owner_json["name"] == "Suresh Kumar"


# ---------------------------------------------------------------------------
# AC-3 / AC-4 / AC-5 — duplicate detection
# ---------------------------------------------------------------------------

def test_AC3_signup_duplicate_phone_409(client):
    """Spec F1 §14 AC-3: a second signup with the same phone is 409."""
    payload, _token, _owner = new_owner(client)
    r = client.post(f"{AUTH}/signup", json=payload)
    assert r.status_code == 409, r.text
    assert r.json() == {"detail": "an account with this phone already exists"}


def test_AC3_duplicate_signup_does_not_replace_account(client):
    """Spec F1 §14 AC-3: the rejected signup creates no second account.

    The original password still works and the rejected one never does, so the
    existing row was neither duplicated nor overwritten.
    """
    payload, _token, owner_json = new_owner(client, name="First Owner")
    r = client.post(
        f"{AUTH}/signup",
        json={**payload, "name": "Second Owner", "password": "different-pw-999"},
    )
    assert r.status_code == 409, r.text

    ok = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": payload["password"]}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["owner"]["id"] == owner_json["id"]
    assert ok.json()["owner"]["name"] == "First Owner"

    bad = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": "different-pw-999"}
    )
    assert bad.status_code == 401, bad.text


@pytest.mark.parametrize("fmt", ["{d}", "0{d}", "91{d}", "+91{d}", "+91-{a}-{b}", "{a} {b}"])
def test_AC4_duplicate_phone_other_format_409(client, fmt):
    """Spec F1 §14 AC-4: the same number in another format is still 409."""
    digits = unique_digits()
    first = client.post(f"{AUTH}/signup", json=signup_payload(phone=f"+91{digits}"))
    assert first.status_code == 201, first.text

    variant = fmt.format(d=digits, a=digits[:5], b=digits[5:])
    r = client.post(f"{AUTH}/signup", json=signup_payload(phone=variant))
    assert r.status_code == 409, f"{variant} -> {r.status_code} {r.text}"
    assert r.json() == {"detail": "an account with this phone already exists"}


def test_AC5_signup_duplicate_email_409_case_insensitive(client):
    """Spec F1 §14 AC-5: an already-registered email (any case) is 409."""
    email = unique_email()
    first = client.post(f"{AUTH}/signup", json=signup_payload(email=email))
    assert first.status_code == 201, first.text
    assert first.json()["owner"]["email"] == email.lower()

    r = client.post(f"{AUTH}/signup", json=signup_payload(email=email.upper()))
    assert r.status_code == 409, r.text
    assert r.json() == {"detail": "an account with this email already exists"}


# ---------------------------------------------------------------------------
# AC-6 / AC-7 — phone normalisation and rejection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fmt",
    [
        "{d}",
        "0{d}",
        "91{d}",
        "+91{d}",
        "+91 {a} {b}",
        "+91-{a}-{b}",
        "{a} {b}",
        "({a}) {b}",
        "{a}.{b}",
        " {d} ",
    ],
)
def test_AC6_signup_normalises_phone(client, fmt):
    """Spec F1 §14 AC-6 / §6 rule 2: accepted shapes all persist as +91XXXXXXXXXX."""
    digits = unique_digits()
    raw = fmt.format(d=digits, a=digits[:5], b=digits[5:])
    r = client.post(f"{AUTH}/signup", json=signup_payload(phone=raw))
    assert r.status_code == 201, f"{raw!r} -> {r.status_code} {r.text}"
    assert r.json()["owner"]["phone"] == f"+91{digits}"


@pytest.mark.parametrize(
    "bad",
    [
        "12345",
        "0512345678",
        "98765432100",
        "abcdefghij",
        "",
        "   ",
        "5876543210",
        "+449876543210",
        "+1 415 555 0132",
        "919876543",
        "9876543210x",
    ],
)
def test_AC7_signup_invalid_phone_422(client, bad):
    """Spec F1 §14 AC-7: an unparseable phone is 422 and creates no owner."""
    r = client.post(f"{AUTH}/signup", json=signup_payload(phone=bad))
    assert r.status_code == 422, f"{bad!r} -> {r.status_code} {r.text}"
    # no account was created: the same string can never be logged in with
    login = client.post(f"{AUTH}/login", json={"identifier": bad, "password": DEFAULT_PASSWORD})
    assert login.status_code != 200, login.text


def test_AC7_422_body_is_fastapi_validation_shape(client):
    """Spec F1 §7: validation failures use FastAPI's validation body."""
    r = client.post(f"{AUTH}/signup", json=signup_payload(phone="12345"))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail, r.text
    assert "loc" in detail[0] and "msg" in detail[0]


# ---------------------------------------------------------------------------
# AC-8 — password length
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pw", ["", "short", "1234567"])
def test_AC8_signup_short_password_422(client, pw):
    """Spec F1 §14 AC-8: a password shorter than 8 characters is 422."""
    r = client.post(f"{AUTH}/signup", json=signup_payload(password=pw))
    assert r.status_code == 422, f"{pw!r} -> {r.status_code} {r.text}"


def test_AC8_signup_password_max_128(client):
    """Spec F1 §6 rule 6: 128 characters is allowed, 129 is 422."""
    ok = client.post(f"{AUTH}/signup", json=signup_payload(password="a" * 128))
    assert ok.status_code == 201, ok.text
    too_long = client.post(f"{AUTH}/signup", json=signup_payload(password="a" * 129))
    assert too_long.status_code == 422, too_long.text


def test_AC8_long_password_round_trips_on_login(client):
    """Spec F1 §6 rule 6: a 128-character password can be used to log in."""
    payload, _token, _owner = new_owner(client, password="b" * 128)
    r = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": "b" * 128}
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# AC-9 — email is optional
# ---------------------------------------------------------------------------

def test_AC9_signup_without_email(client):
    """Spec F1 §14 AC-9: omitted email, "" and null all store NULL and coexist."""
    omitted = client.post(f"{AUTH}/signup", json=signup_payload())
    assert omitted.status_code == 201, omitted.text
    assert omitted.json()["owner"]["email"] is None

    empty = client.post(f"{AUTH}/signup", json=signup_payload(email=""))
    assert empty.status_code == 201, empty.text
    assert empty.json()["owner"]["email"] is None

    explicit_null = client.post(f"{AUTH}/signup", json=signup_payload(email=None))
    assert explicit_null.status_code == 201, explicit_null.text
    assert explicit_null.json()["owner"]["email"] is None

    ids = {
        omitted.json()["owner"]["id"],
        empty.json()["owner"]["id"],
        explicit_null.json()["owner"]["id"],
    }
    assert len(ids) == 3, "three distinct accounts with NULL email must coexist"


def test_AC9_signup_email_lowercased_and_trimmed(client):
    """Spec F1 §6 rule 4: email is trimmed and lowercased before storage."""
    email = unique_email()
    r = client.post(f"{AUTH}/signup", json=signup_payload(email=f"  {email.upper()}  "))
    assert r.status_code == 201, r.text
    assert r.json()["owner"]["email"] == email.lower()


@pytest.mark.parametrize("bad", ["not-an-email", "a@", "@example.com", "a@b"])
def test_AC9_signup_invalid_email_422(client, bad):
    """Spec F1 §7: an invalid email is 422."""
    r = client.post(f"{AUTH}/signup", json=signup_payload(email=bad))
    assert r.status_code == 422, f"{bad!r} -> {r.status_code} {r.text}"


def test_signup_missing_fields_422(client):
    """Spec F1 §7: a missing required field is 422."""
    for omit in ("name", "phone", "password"):
        payload = signup_payload()
        payload.pop(omit)
        r = client.post(f"{AUTH}/signup", json=payload)
        assert r.status_code == 422, f"missing {omit} -> {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# AC-14 — blank name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["", "   ", "\t", "\n  \n"])
def test_AC14_signup_blank_name_422(client, name):
    """Spec F1 §14 AC-14: a blank or whitespace-only name is 422."""
    r = client.post(f"{AUTH}/signup", json=signup_payload(name=name))
    assert r.status_code == 422, f"{name!r} -> {r.status_code} {r.text}"


def test_AC14_signup_name_over_120_chars_422(client):
    """Spec F1 §7: name is 1-120 characters after trimming."""
    r = client.post(f"{AUTH}/signup", json=signup_payload(name="x" * 121))
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# AC-10 / AC-11 / AC-12 — login success paths
# ---------------------------------------------------------------------------

def test_AC10_login_with_phone(client):
    """Spec F1 §14 AC-10: login with the registered phone returns 200 + token."""
    payload, _token, owner_json = new_owner(client)
    r = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": payload["password"]}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_auth_response(body)
    assert body["owner"]["id"] == owner_json["id"]
    me = client.get(f"{AUTH}/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200 and me.json()["id"] == owner_json["id"]


def test_AC11_login_with_email_mixed_case(client):
    """Spec F1 §14 AC-11: login with the registered email (any case) returns 200."""
    email = unique_email()
    payload, _token, owner_json = new_owner(client, email=email)
    r = client.post(
        f"{AUTH}/login",
        json={"identifier": email.upper(), "password": payload["password"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["owner"]["id"] == owner_json["id"]


@pytest.mark.parametrize("fmt", ["{d}", "0{d}", "91{d}", "+91{d}", "+91-{a}-{b}", "{a} {b}"])
def test_AC12_login_accepts_any_phone_format(client, fmt):
    """Spec F1 §14 AC-12: login accepts the phone in any supported format."""
    digits = unique_digits()
    payload, _token, owner_json = new_owner(client, phone=f"+91{digits}")
    identifier = fmt.format(d=digits, a=digits[:5], b=digits[5:])
    r = client.post(
        f"{AUTH}/login", json={"identifier": identifier, "password": payload["password"]}
    )
    assert r.status_code == 200, f"{identifier!r} -> {r.status_code} {r.text}"
    assert r.json()["owner"]["id"] == owner_json["id"]


# ---------------------------------------------------------------------------
# AC-13 / AC-14b / AC-15 — login failures are generic 401s
# ---------------------------------------------------------------------------

def test_AC13_login_wrong_password_401(client):
    """Spec F1 §14 AC-13: a wrong password returns 401 with the generic detail."""
    payload, _token, _owner = new_owner(client)
    r = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": "wrong-password"}
    )
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": GENERIC_LOGIN_DETAIL}


def test_AC14b_unknown_identifier_body_identical(client):
    """Spec F1 §14 AC-14b: unknown identifier and wrong password are byte-identical."""
    payload, _token, _owner = new_owner(client)
    wrong_pw = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": "wrong-password"}
    )
    unknown = client.post(
        f"{AUTH}/login",
        json={"identifier": unique_digits(), "password": DEFAULT_PASSWORD},
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.content == unknown.content, (wrong_pw.text, unknown.text)


def test_AC14b_unknown_email_body_identical(client):
    """Spec F1 §6 rule 8: an unregistered email is the same generic 401."""
    r = client.post(
        f"{AUTH}/login",
        json={"identifier": unique_email("nobody"), "password": DEFAULT_PASSWORD},
    )
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": GENERIC_LOGIN_DETAIL}


@pytest.mark.parametrize(
    "identifier",
    ["not-a-phone", "12345", "0512345678", "98765432100", "+449876543210", "@", "   "],
)
def test_AC15_login_malformed_identifier_401_not_422(client, identifier):
    """Spec F1 §14 AC-15: a malformed identifier is 401, never 422."""
    r = client.post(
        f"{AUTH}/login", json={"identifier": identifier, "password": DEFAULT_PASSWORD}
    )
    assert r.status_code == 401, f"{identifier!r} -> {r.status_code} {r.text}"
    assert r.json() == {"detail": GENERIC_LOGIN_DETAIL}


def test_AC15_login_empty_identifier_401_not_422(client):
    """Spec F1 §6 rule 8: an empty identifier is still a generic 401, not 422.

    Rule 8 allows 422 only for a missing / non-string field (§7); an empty
    string is "an identifier that is neither a valid phone nor an email".
    """
    r = client.post(f"{AUTH}/login", json={"identifier": "", "password": DEFAULT_PASSWORD})
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": GENERIC_LOGIN_DETAIL}


def test_AC15_login_short_password_401_not_422(client):
    """Spec F1 §6 rule 8 / §7: login never 422s on a too-short password."""
    payload, _token, _owner = new_owner(client)
    r = client.post(f"{AUTH}/login", json={"identifier": payload["phone"], "password": "x"})
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": GENERIC_LOGIN_DETAIL}


def test_AC15_login_empty_password_401_not_422(client):
    """Spec F1 §6 rule 8: an empty password is a generic 401, not 422."""
    payload, _token, _owner = new_owner(client)
    r = client.post(f"{AUTH}/login", json={"identifier": payload["phone"], "password": ""})
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": GENERIC_LOGIN_DETAIL}


def test_login_missing_field_422(client):
    """Spec F1 §7: a missing identifier/password field is 422."""
    assert client.post(f"{AUTH}/login", json={"password": "x" * 9}).status_code == 422
    assert client.post(f"{AUTH}/login", json={"identifier": "x"}).status_code == 422


def test_login_non_string_identifier_422(client):
    """Spec F1 §7: a non-string identifier is 422."""
    r = client.post(f"{AUTH}/login", json={"identifier": 9876543210, "password": "x" * 9})
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# AC-16 — /auth/me
# ---------------------------------------------------------------------------

def test_AC16_me_with_token(client):
    """Spec F1 §14 AC-16: /auth/me returns the caller's own owner record."""
    email = unique_email()
    payload, token, owner_json = new_owner(client, name="Suresh Kumar", email=email)
    r = client.get(f"{AUTH}/me", headers=bearer(token))
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_owner_shape(body)
    assert body == owner_json, (body, owner_json)
    assert body["name"] == "Suresh Kumar"
    assert body["email"] == email.lower()
    assert body["phone"].startswith("+91")


def test_AC16_me_with_login_token(client):
    """Spec F1 §14 AC-16: a token obtained from login also resolves /auth/me."""
    payload, _signup_token, owner_json = new_owner(client)
    login = client.post(
        f"{AUTH}/login", json={"identifier": payload["phone"], "password": payload["password"]}
    )
    r = client.get(f"{AUTH}/me", headers=bearer(login.json()["access_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == owner_json["id"]


# ---------------------------------------------------------------------------
# AC-17 / AC-18 / AC-19 / AC-20 — token rejection paths
# ---------------------------------------------------------------------------

def test_AC17_me_without_token_401(client):
    """Spec F1 §14 AC-17: no Authorization header returns 401, not 403."""
    r = client.get(f"{AUTH}/me")
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_AC17_me_without_token_www_authenticate_header(client):
    """Spec F1 §6 rule 10: the 401 carries WWW-Authenticate: Bearer."""
    r = client.get(f"{AUTH}/me")
    assert r.headers.get("www-authenticate") == "Bearer", dict(r.headers)


@pytest.mark.parametrize(
    "header",
    [
        "Bearer garbage",
        "Basic abc",
        "Bearer",
        "",
        "bearer garbage",
        "Bearer a.b.c",
        "Token abcdef",
    ],
)
def test_AC18_me_with_malformed_token_401(client, header):
    """Spec F1 §14 AC-18: malformed tokens and non-Bearer schemes are 401."""
    r = client.get(f"{AUTH}/me", headers={"Authorization": header})
    assert r.status_code == 401, f"{header!r} -> {r.status_code} {r.text}"
    assert r.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_AC18_me_with_empty_bearer_value_401():
    """Spec F1 §14 AC-18: "Bearer " (scheme, empty token) is 401.

    httpx refuses to send a header value with a trailing space, so this exact
    case from the spec's test plan is sent over a raw socket.
    """
    status, body = raw_get("/api/v1/auth/me", {"Authorization": "Bearer "})
    assert status == 401, (status, body)
    assert json.loads(body) == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_AC18_me_with_token_signed_by_other_secret_401(client):
    """Spec F1 §14 AC-18: a token signed with another secret is 401."""
    _payload, _token, owner_json = new_owner(client)
    forged = jwt.encode(
        {
            "sub": owner_json["id"],
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        },
        "a-totally-different-secret-value-0001",
        algorithm="HS256",
    )
    r = client.get(f"{AUTH}/me", headers=bearer(forged))
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_AC18_me_with_alg_none_token_401(client):
    """Spec F1 §6 rule 9: only HS256 is accepted — an unsigned token is 401."""
    _payload, _token, owner_json = new_owner(client)
    unsigned = jwt.encode(
        {
            "sub": owner_json["id"],
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        },
        key="",
        algorithm="none",
    )
    r = client.get(f"{AUTH}/me", headers=bearer(unsigned))
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("sub", ["not-a-uuid", "123", ""])
def test_AC18_me_with_non_uuid_sub_401(client, sub):
    """Spec F1 §6 rule 10: a correctly signed token with a non-UUID sub is 401."""
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": sub,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    r = client.get(f"{AUTH}/me", headers=bearer(token))
    assert r.status_code == 401, f"{sub!r} -> {r.status_code} {r.text}"
    assert r.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_AC18_me_with_token_missing_sub_401(client):
    """Spec F1 §6 rule 10: a signed token without sub is 401."""
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"iat": int(now.timestamp()), "exp": int((now + timedelta(days=1)).timestamp())},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    r = client.get(f"{AUTH}/me", headers=bearer(token))
    assert r.status_code == 401, r.text


def test_AC19_me_with_expired_token_401(client):
    """Spec F1 §14 AC-19: an expired token is 401.

    Server time cannot be frozen, so the token is forged with the configured
    JWT secret and an `exp` 31 days in the past — the same shape the app's
    own `create_access_token(..., now=...)` would produce.
    """
    _payload, _token, owner_json = new_owner(client)
    # iat far enough in the past that iat + the configured lifetime is also past
    past = datetime.now(timezone.utc) - timedelta(minutes=JWT_EXPIRES_MINUTES) - timedelta(days=1)
    expired = jwt.encode(
        {
            "sub": owner_json["id"],
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=JWT_EXPIRES_MINUTES)).timestamp()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    r = client.get(f"{AUTH}/me", headers=bearer(expired))
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_AC20_me_with_unknown_owner_token_401(client):
    """Spec F1 §14 AC-20: a valid token for a non-existent owner is 401."""
    import uuid as _uuid

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(_uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    r = client.get(f"{AUTH}/me", headers=bearer(token))
    assert r.status_code == 401, r.text
    assert r.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


# ---------------------------------------------------------------------------
# AC-21 — the password never comes back
# ---------------------------------------------------------------------------

def test_AC21_no_password_in_any_response_body(client):
    """Spec F1 §14 AC-21: no response body contains the password or its hash."""
    payload = signup_payload(password="super-secret-123", email=unique_email())
    signup = client.post(f"{AUTH}/signup", json=payload)
    assert signup.status_code == 201, signup.text
    token = signup.json()["access_token"]
    login = client.post(
        f"{AUTH}/login",
        json={"identifier": payload["phone"], "password": payload["password"]},
    )
    me = client.get(f"{AUTH}/me", headers=bearer(token))

    for label, response in (("signup", signup), ("login", login), ("me", me)):
        text = response.text
        assert "super-secret-123" not in text, label
        assert "password" not in text.lower(), f"{label}: {text}"
        assert "argon2" not in text.lower(), label


def test_AC21_duplicate_409_body_leaks_nothing(client):
    """Spec F1 §6 rule 12: the 409 body is only {"detail": ...}."""
    payload, _token, _owner = new_owner(client, password="super-secret-123")
    r = client.post(f"{AUTH}/signup", json=payload)
    assert r.status_code == 409
    assert set(r.json().keys()) == {"detail"}
    assert "super-secret-123" not in r.text


def test_AC21_422_body_does_not_echo_password(client):
    """Spec F1 §6 rule 6: a validation failure must not echo the plaintext.

    FastAPI's 422 body includes the offending `input` value; for a password
    field that would write the plaintext into logs and the client.
    """
    r = client.post(f"{AUTH}/signup", json=signup_payload(password="tiny"))
    assert r.status_code == 422
    assert "tiny" not in r.text, r.text


# ---------------------------------------------------------------------------
# AC-22 — isolation between owners
# ---------------------------------------------------------------------------

def test_AC22_me_isolation_between_owners(client):
    """Spec F1 §14 AC-22: each token returns only its own owner."""
    a_payload, a_token, a_owner = new_owner(client, name="Owner A", email=unique_email("a"))
    b_payload, b_token, b_owner = new_owner(client, name="Owner B", email=unique_email("b"))
    assert a_owner["id"] != b_owner["id"]

    a = client.get(f"{AUTH}/me", headers=bearer(a_token)).json()
    b = client.get(f"{AUTH}/me", headers=bearer(b_token)).json()

    assert a["id"] == a_owner["id"] and b["id"] == b_owner["id"]
    assert a["phone"] != b["phone"] and a["email"] != b["email"]
    for field in ("id", "phone", "email", "name"):
        assert a[field] != b[field], field
        assert b_owner[field] != a[field], f"A's token leaked B's {field}"


def test_AC22_login_returns_only_the_matching_owner(client):
    """Spec F1 §6 rule 11: login resolves exactly the identified account."""
    a_payload, _a_token, a_owner = new_owner(client, name="Owner A")
    b_payload, _b_token, b_owner = new_owner(client, name="Owner B")
    r = client.post(
        f"{AUTH}/login",
        json={"identifier": a_payload["phone"], "password": a_payload["password"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["owner"]["id"] == a_owner["id"]

    # A's password must not open B's account.
    cross = client.post(
        f"{AUTH}/login",
        json={"identifier": b_payload["phone"], "password": "qa-secret-123-other"},
    )
    assert cross.status_code == 401, cross.text


# ---------------------------------------------------------------------------
# Published contract (spec §7 vs /openapi.json)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def openapi():
    import httpx

    from conftest import BASE_URL

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        r = c.get("/openapi.json")
        r.raise_for_status()
        return r.json()


def test_contract_paths_present(openapi):
    """Spec F1 §7: the three auth routes are published under /api/v1."""
    paths = openapi["paths"]
    assert "post" in paths["/api/v1/auth/signup"]
    assert "post" in paths["/api/v1/auth/login"]
    assert "get" in paths["/api/v1/auth/me"]


def test_contract_documented_status_codes(openapi):
    """Spec F1 §7: signup documents 201/409/422, login 200/401/422, me 200/401."""
    paths = openapi["paths"]
    assert {"201", "409", "422"} <= set(paths["/api/v1/auth/signup"]["post"]["responses"])
    assert {"200", "401", "422"} <= set(paths["/api/v1/auth/login"]["post"]["responses"])
    assert {"200", "401"} <= set(paths["/api/v1/auth/me"]["get"]["responses"])


def test_contract_response_schemas(openapi):
    """Spec F1 §7: AuthResponse / OwnerRead fields, and no password_hash."""
    schemas = openapi["components"]["schemas"]
    assert set(schemas["AuthResponse"]["properties"]) == {
        "access_token",
        "token_type",
        "owner",
    }
    assert schemas["AuthResponse"]["properties"]["token_type"].get("const") == "bearer"
    owner = schemas["OwnerRead"]["properties"]
    assert set(owner) == {"id", "name", "phone", "email", "created_at"}
    assert "password_hash" not in owner


def test_contract_signup_request_schema(openapi):
    """Spec F1 §7: SignupRequest = name, phone, email?, password (8-128)."""
    props = openapi["components"]["schemas"]["SignupRequest"]["properties"]
    assert set(props) == {"name", "phone", "email", "password"}
    assert props["password"]["minLength"] == 8
    assert props["password"]["maxLength"] == 128
    assert props["name"]["maxLength"] == 120
    required = set(openapi["components"]["schemas"]["SignupRequest"]["required"])
    assert required == {"name", "phone", "password"}


def test_contract_me_requires_bearer_security(openapi):
    """Spec F1 §7: /auth/me is the only auth-required route in F1."""
    me = openapi["paths"]["/api/v1/auth/me"]["get"]
    assert me.get("security"), me
    assert "HTTPBearer" in me["security"][0]
    assert not openapi["paths"]["/api/v1/auth/signup"]["post"].get("security")
    assert not openapi["paths"]["/api/v1/auth/login"]["post"].get("security")


def test_contract_no_out_of_scope_endpoints(openapi):
    """Spec F1 §3: F1 ships no resources of its own beyond /auth.

    Updated for F2, which legitimately adds GET/PATCH /api/v1/pg. The check is
    now "nothing beyond what the specs delivered so far promise".
    """
    assert set(openapi["paths"]) == {
        "/api/v1/health",
        "/api/v1/auth/signup",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/pg",  # F2
    }, set(openapi["paths"])


# ---------------------------------------------------------------------------
# Conventions / misc
# ---------------------------------------------------------------------------

def test_signup_method_not_allowed(client):
    """CLAUDE.md §8: /auth/signup is POST-only."""
    assert client.get(f"{AUTH}/signup").status_code == 405


def test_me_is_get_only(client):
    """CLAUDE.md §8: /auth/me is GET-only."""
    assert client.post(f"{AUTH}/me").status_code == 405


def test_created_at_is_timezone_aware_ist(client):
    """Spec F1 §7 example / §6 rule 13: created_at is tz-aware (IST offset)."""
    _payload, _token, owner_json = new_owner(client)
    parsed = datetime.fromisoformat(owner_json["created_at"])
    assert parsed.tzinfo is not None, owner_json["created_at"]
    offset = parsed.utcoffset()
    assert offset == timedelta(hours=5, minutes=30), (
        f"spec §7 shows created_at in IST (+05:30), got {owner_json['created_at']!r}"
    )


def test_health_still_ok(client):
    """Sanity: F0.1's health endpoint is unaffected by F1."""
    r = client.get(f"{API}/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# §11 risk — concurrent duplicate signup (the IntegrityError race)
# ---------------------------------------------------------------------------

def test_concurrent_duplicate_signup_yields_one_201_and_409s():
    """Spec F1 §11: a duplicate-signup race must end in 409, never a 500."""
    import httpx
    from concurrent.futures import ThreadPoolExecutor

    from conftest import BASE_URL

    payload = signup_payload()

    def attempt(_i):
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
            r = c.post(f"{AUTH}/signup", json=payload)
            return r.status_code, r.text

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))

    codes = [code for code, _ in results]
    assert codes.count(201) == 1, results
    assert all(c in (201, 409) for c in codes), results
    for code, text in results:
        if code == 409:
            assert json.loads(text) == {
                "detail": "an account with this phone already exists"
            }, text
