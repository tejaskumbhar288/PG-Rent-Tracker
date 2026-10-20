# F1 — Owner signup and login

| | |
|---|---|
| Phase | Phase 1 — Owner account and PG |
| Status | Draft |
| Depends on | F0.1 Backend skeleton ✅ (FastAPI app factory, settings, SQLAlchemy `Base`/session, Alembic at `0001_baseline`, pytest `client`/`db` fixtures) · F0.2 Mobile skeleton ✅ (Expo Router tabs, `apiGet` client, TanStack Query provider, Jest) |
| Used by | F2 (PG profile: `GET`/`PATCH /pg`, `get_current_pg`) · F3–F13 (every route is scoped by `get_current_owner` → the owner's PG; every mobile screen sits behind the auth gate) |
| Last updated | 2026-10-20 |

## 1. Summary

The owner can create an account with their name, phone and a password, and log in afterwards with either their
phone or their email. Signup also creates the owner's single PG (the row every later feature scopes to), so the
app has a tenant-less but complete account from the first screen. The mobile app stores the JWT in
`expo-secure-store`, so the owner stays logged in across app restarts and sees the Dashboard instead of the login
screen; Logout in Settings clears it. This is the gate for every feature after it: without it there is no owner to
attach rooms, tenants, rent records or payments to.

## 2. User stories

- As a PG owner, I want to create an account with my phone number and a password, so that my PG's data is mine and nobody else can see it.
- As a PG owner, I want to log in with my phone number *or* my email, so that I don't have to remember which one I signed up with.
- As a PG owner, I want to type my number the way I always do (`98765 43210`), so that I don't have to think about country codes.
- As a PG owner, I want to stay logged in when I reopen the app, so that I'm not typing a password every time I check who has paid.
- As a PG owner, I want a Logout button, so that I can hand my phone to someone without exposing my tenants' details.

## 3. Scope

**In scope**
- `owners` table + `pgs` table and one Alembic migration for both (see §12 Q1 — `pgs` is needed here because signup creates the PG).
- Shared model mixins for `id` (UUID generated in Python), `created_at`, `updated_at` — the pattern every later table reuses.
- Password hashing (argon2) and JWT access tokens (HS256) in `app/core/security.py`.
- `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.
- `get_current_owner` dependency in `app/core/deps.py`, returning **401** (not 403) when the token is missing, malformed or expired.
- Phone normalisation to E.164 in `app/services/phone.py`, used by the signup schema and by login lookup.
- Per-test database cleanup in `tests/conftest.py` plus owner/auth fixtures (the F0.1 conftest has no row cleanup — see §11).
- Mobile: `(auth)/login` and `(auth)/signup` screens, token in `expo-secure-store`, auth gate that lands a logged-in owner on the Dashboard, `Authorization` header on API calls, Logout in Settings.

**Out of scope** (do not build)
- `GET`/`PATCH /pg` and the `get_current_pg` dependency — **F2**. F1 only creates the row.
- Any PG-editing UI. Settings gets the logged-in owner's name/phone and a Logout button, nothing more.
- Refresh tokens, token rotation, "remember me" toggle, logout-everywhere/token revocation.
- Password reset / forgot password, email verification, phone OTP (OTP is explicitly out of scope in CLAUDE.md §4).
- Rate limiting, lockout after N failed logins, CAPTCHA.
- Social login, multi-owner/staff accounts, roles or permissions.
- Rooms, tenants, rent, payments and their screens (F3+).

## 4. Current state of the codebase

| Path | What's there | How F1 uses it |
|---|---|---|
| `backend/app/main.py` | `create_app()` includes `health.router` with prefix `/api/v1` | add `app.include_router(auth.router, prefix="/api/v1", tags=["auth"])` |
| `backend/app/core/config.py` | `Settings` (`database_url`, `test_database_url`, `jwt_secret`, `tz`), `get_settings()` cached | add `jwt_algorithm`, `jwt_expires_minutes` |
| `backend/app/db/base.py` | `Base(DeclarativeBase)` only — no mixins yet | add the model mixins (§8) |
| `backend/app/db/session.py` | `engine`, `SessionLocal`, `get_db()` dependency | reused unchanged by `get_current_owner` |
| `backend/app/models/` | **does not exist** | create with `__init__.py`, `owner.py`, `pg.py` |
| `backend/app/schemas/` | `health.py` only; pattern = one small `BaseModel` per response | add `auth.py`, `owner.py` |
| `backend/app/services/` | **does not exist** | create with `auth.py`, `phone.py` |
| `backend/app/core/deps.py` | **does not exist** | create with `get_current_owner` |
| `backend/app/api/routes/health.py` | router pattern to copy: explicit `response_model`, documented error `responses={}`, `HTTPException(status_code=…, detail="lowercase sentence")` | copy for `auth.py` |
| `backend/alembic/versions/0001_baseline.py` | empty baseline, `down_revision = None` | F1's migration sets `down_revision = "0001_baseline"` |
| `backend/alembic/env.py` | `target_metadata = Base.metadata`; has a comment marking where to import models | import `app.models` there so autogenerate sees the tables |
| `backend/tests/conftest.py` | session-scoped `_create_schema` (create_all/drop_all), `db`, `client` (overrides `get_db` with the test session) | extend: per-test truncate, `owner_factory`, `auth_headers`, `authed_client` |
| `mobile/src/api/client.ts` | `apiGet`, `ApiError(status)`, 5 s abort timeout, comment "No auth header yet (added in F1)" | add bearer header + `apiPost` + `detail` parsing |
| `mobile/src/app/_layout.tsx` | `QueryClientProvider` → `ThemeProvider` → `AnimatedSplashOverlay` + `AppTabs` | wrap in `AuthProvider`, choose auth stack vs tabs |
| `mobile/src/app/settings.tsx` | backend health card using `useHealth()` + `StatusPill` | add an ACCOUNT card + Logout |
| `mobile/src/constants/theme.ts` | `Colors` (incl. `statusError`, `statusWarning`), `Spacing`, `BottomTabInset` | reuse for form errors and buttons |
| `mobile/jest.config.js` | `jest-expo` preset, maps `@/*` and `*.css` | add `expo-secure-store` mock in the auth-storage test |

Patterns to follow:
- Routes stay thin; logic lives in `app/services/` (CLAUDE.md §9). Every route declares a Pydantic `response_model`.
- Errors are `{"detail": "..."}` via `HTTPException`, lowercase message, documented in the route's `responses=`.
- Mobile keeps logic out of screens: pure helpers in `src/lib/`, data access in `src/api/` hooks (CLAUDE.md §9).
- Tests are plain functions taking the `client` fixture, asserting status code *and* body.

## 5. Data model changes

### `owners`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | — | PK, `default=uuid.uuid4` **in Python** (CLAUDE.md §7 — never a DB function) |
| `name` | `VARCHAR(120)` | no | — | trimmed; must be non-empty after trimming |
| `phone` | `VARCHAR(16)` | no | — | **UNIQUE**, E.164 (`+91XXXXXXXXXX`) |
| `email` | `VARCHAR(255)` | yes | `NULL` | **UNIQUE**, stored lowercased (Postgres allows many NULLs under a unique constraint) |
| `password_hash` | `VARCHAR(255)` | no | — | argon2 encoded hash; never returned by the API |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | `onupdate=func.now()` |

Constraints / indexes: `pk_owners`, `uq_owners_phone`, `uq_owners_email` (the unique constraints provide the lookup indexes for login).

### `pgs`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | — | PK, `uuid.uuid4` in Python |
| `owner_id` | `UUID` | no | — | FK → `owners.id`, `ON DELETE CASCADE`, **indexed** |
| `name` | `VARCHAR(120)` | no | `'My PG'` applied in the service | FEATURES.md F2: name defaults to "My PG" |
| `address` | `TEXT` | yes | `NULL` | |
| `default_rent_due_day` | `SMALLINT` | no | `5` | `CHECK (default_rent_due_day BETWEEN 1 AND 28)` → `ck_pgs_default_rent_due_day_range` |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

No unique constraint on `(owner_id)`: the DB supports several PGs per owner (CLAUDE.md §3); only the UI is single-PG.

**Migration:** `backend/alembic/versions/0002_owners_and_pgs.py`, `down_revision = "0001_baseline"`, creating both tables with
their constraints; `downgrade()` drops `pgs` then `owners`. Hand-write or autogenerate, but review it — autogenerate does
not emit the `CHECK` constraint unless it is declared in `__table_args__`. No Postgres-18-only features (CLAUDE.md §5).

## 6. Business rules

1. **UUIDs are generated in Python** (`uuid.uuid4()`), never by a DB function (CLAUDE.md §7).
2. **Phone is normalised to E.164 before it is stored or compared** (CLAUDE.md §7). `normalize_phone` strips spaces, hyphens,
   dots, parentheses and non-breaking spaces, then accepts exactly these shapes, all mapping to `+91XXXXXXXXXX`:
   | Input | Rule | Result |
   |---|---|---|
   | `9876543210` | 10 digits, first digit 6–9 | `+919876543210` |
   | `09876543210` | 11 digits, leading `0` | `+919876543210` |
   | `919876543210` | 12 digits, leading `91` | `+919876543210` |
   | `+91 98765 43210`, `+91-98765-43210` | `+91` then 10 digits, first 6–9 | `+919876543210` |
   Anything else (too short, too long, letters, a 10-digit number starting 0–5, another country code) raises `ValueError`.
3. **Signup normalises first, then checks uniqueness**, so `98765 43210` and `+919876543210` are the same account (rule 2 + the
   `uq_owners_phone` constraint). A duplicate phone is **409**, never 422 and never a second account.
4. **Email is optional.** When present it is trimmed and lowercased before storage and comparison, so `Ram@X.com` and
   `ram@x.com` are the same account; a duplicate is **409**. When absent/empty it is stored as `NULL`.
5. **Signup creates exactly one `pgs` row** for the new owner in the same transaction, with `name = "My PG"`,
   `address = NULL`, `default_rent_due_day = 5`. If either insert fails, neither is committed.
6. **Passwords are hashed with argon2**; the plaintext is never stored, logged or returned. Minimum length 8, maximum 128
   characters, no composition rules (the user is one non-technical owner — CLAUDE.md §2).
7. **Login accepts one `identifier` field**: if it contains `@` it is matched against `owners.email` (lowercased), otherwise
   it is normalised as a phone and matched against `owners.phone`.
8. **Login failures are indistinguishable.** Unknown identifier, wrong password *and* an identifier that is not a valid phone
   or email all return **401** with the identical body `{"detail": "invalid phone/email or password"}`. Login never returns
   422 for a malformed identifier — that would reveal which accounts exist.
9. **A JWT is issued on both signup and login**: HS256, signed with `settings.jwt_secret`, claims `sub` (owner id as a string),
   `iat`, `exp` (`iat + settings.jwt_expires_minutes`, default 30 days — §12 Q2). No other claims; no owner data in the token.
10. **`get_current_owner` returns 401** when the `Authorization` header is absent, is not `Bearer <token>`, fails signature
    verification, is expired, has a `sub` that is not a UUID, or names an owner that no longer exists. Body:
    `{"detail": "not authenticated"}`, with a `WWW-Authenticate: Bearer` header.
11. **An owner only ever sees their own row.** `GET /auth/me` reads the owner resolved from the token's `sub` and nothing else
    (CLAUDE.md §7 — never return another owner's data). This is the base case of the PG scoping every later feature builds on.
12. **`password_hash` never appears in a response.** The response schemas list fields explicitly rather than dumping the model.
13. **Timestamps are `TIMESTAMPTZ`**; the app's display timezone is `Asia/Kolkata` (CLAUDE.md §7). F1 has no date arithmetic,
    so IST matters only in that stored instants are timezone-aware.
14. **`name` is trimmed**; a name that is empty or whitespace-only is **422**.

## 7. API contract

All paths are under the `/api/v1` prefix (CLAUDE.md §8). JSON only.

### `POST /api/v1/auth/signup` — no auth

Request (`SignupRequest`):

| Field | Type | Validation |
|---|---|---|
| `name` | `str` | required, trimmed, 1–120 chars after trimming |
| `phone` | `str` | required, normalised by `normalize_phone`; `ValueError` → 422 |
| `email` | `EmailStr \| None` | optional, lowercased; `""` treated as `None` |
| `password` | `str` | required, 8–128 chars |

Response **201** (`AuthResponse`):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "owner": {
    "id": "3f1c7f4e-8e2a-4d3b-9b7a-2c9f0a1b5d61",
    "name": "Suresh Kumar",
    "phone": "+919876543210",
    "email": null,
    "created_at": "2026-10-20T09:15:00+05:30"
  }
}
```

Errors:

| Status | `detail` | When |
|---|---|---|
| 409 | `an account with this phone already exists` | phone (after normalisation) is taken — incl. the `IntegrityError` race |
| 409 | `an account with this email already exists` | email (lowercased) is taken |
| 422 | FastAPI validation body | unparseable phone, invalid email, password < 8 or > 128, blank name, missing field |

### `POST /api/v1/auth/login` — no auth

Request (`LoginRequest`): `identifier: str` (phone in any accepted format, or email), `password: str`.

Response **200**: the same `AuthResponse` body as signup.

Errors:

| Status | `detail` | When |
|---|---|---|
| 401 | `invalid phone/email or password` | unknown identifier, wrong password, **or** an identifier that is neither a valid phone nor an email (rule 8) |
| 422 | FastAPI validation body | `identifier` or `password` missing / not a string |

### `GET /api/v1/auth/me` — **auth required**

Response **200** (`OwnerRead`):

```json
{
  "id": "3f1c7f4e-8e2a-4d3b-9b7a-2c9f0a1b5d61",
  "name": "Suresh Kumar",
  "phone": "+919876543210",
  "email": "suresh@example.com",
  "created_at": "2026-10-20T09:15:00+05:30"
}
```

Errors:

| Status | `detail` | When |
|---|---|---|
| 401 | `not authenticated` | no header, wrong scheme, bad signature, expired, non-UUID `sub`, owner row gone |

**Scoping:** `/auth/me` is inherently self-scoped — the owner id comes from the verified token, never from the request, so
owner A's token cannot address owner B. There is no path parameter to 404 on in F1; the 404-for-another-owner's-resource
convention (CLAUDE.md §8) starts in F2 with `/pg`.

## 8. Backend implementation plan

In order:

1. **`backend/pyproject.toml`** — add runtime deps: `argon2-cffi>=23.1`, `pyjwt>=2.9`, `email-validator>=2.1`
   (for `EmailStr`). No new dev deps: token expiry is tested through `create_access_token(..., now=…)`, so `time-machine`
   waits for F7. Run `uv sync`.
2. **`backend/app/core/config.py`** — extend `Settings`:
   `jwt_algorithm: str = "HS256"`, `jwt_expires_minutes: int = 60 * 24 * 30`.
3. **`backend/.env.example`** — document `JWT_ALGORITHM` and `JWT_EXPIRES_MINUTES` as optional overrides (keep `JWT_SECRET`).
4. **`backend/app/db/base.py`** — add the shared mixins beside `Base`:
   - `class UUIDPrimaryKey:` → `id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)`
   - `class Timestamps:` → `created_at` / `updated_at` as `Mapped[datetime]`, `sa.DateTime(timezone=True)`,
     `server_default=func.now()`, `updated_at` also `onupdate=func.now()`
   (`sa.Uuid` is SQLAlchemy 2.0's portable type and renders as Postgres `UUID`.)
5. **`backend/app/models/__init__.py`** — import `Owner` and `Pg` so `Base.metadata` is complete for Alembic.
6. **`backend/app/models/owner.py`** — `class Owner(UUIDPrimaryKey, Timestamps, Base)`, `__tablename__ = "owners"`, columns per
   §5, `pgs: Mapped[list["Pg"]] = relationship(back_populates="owner", cascade="all, delete-orphan")`.
7. **`backend/app/models/pg.py`** — `class Pg(UUIDPrimaryKey, Timestamps, Base)`, `__tablename__ = "pgs"`, columns per §5,
   `__table_args__ = (CheckConstraint("default_rent_due_day BETWEEN 1 AND 28", name="ck_pgs_default_rent_due_day_range"),)`,
   `owner: Mapped[Owner] = relationship(back_populates="pgs")`.
8. **`backend/alembic/env.py`** — replace the placeholder comment with `from app import models  # noqa: F401`.
9. **`backend/alembic/versions/0002_owners_and_pgs.py`** — as described in §5; verify the generated SQL includes the check
   constraint and both unique constraints.
10. **`backend/app/services/phone.py`**
    - `normalize_phone(raw: str) -> str` — rule 2; raises `ValueError("invalid indian phone number")`.
11. **`backend/app/core/security.py`**
    - `_hasher = argon2.PasswordHasher()`
    - `hash_password(plain: str) -> str`
    - `verify_password(plain: str, hashed: str) -> bool` — returns `False` on `argon2.exceptions.VerifyMismatchError` / `InvalidHash`
    - `create_access_token(owner_id: uuid.UUID, *, now: datetime | None = None) -> str`
    - `decode_access_token(token: str) -> uuid.UUID` — raises `TokenError` (module-level `class TokenError(Exception)`) on any
      `jwt.PyJWTError`, missing `sub`, or non-UUID `sub`
    - `DUMMY_HASH: str` — a precomputed argon2 hash verified against when no owner matches, so login takes similar time
      whether or not the account exists (§11).
12. **`backend/app/services/auth.py`**
    - `class DuplicatePhoneError(Exception)` / `class DuplicateEmailError(Exception)`
    - `signup_owner(db: Session, *, name: str, phone: str, email: str | None, password: str) -> tuple[Owner, Pg]` — uniqueness
      pre-check, insert owner + its `Pg("My PG", default_rent_due_day=5)`, one `db.commit()`, `IntegrityError` → rollback and
      raise the matching duplicate error by constraint name
    - `authenticate_owner(db: Session, *, identifier: str, password: str) -> Owner | None` — rule 7; on no match, verify
      against `DUMMY_HASH` and return `None`
    - `get_owner_by_id(db: Session, owner_id: uuid.UUID) -> Owner | None`
13. **`backend/app/schemas/owner.py`** — `OwnerRead` (`id`, `name`, `phone`, `email`, `created_at`;
    `model_config = ConfigDict(from_attributes=True)`; **no** `password_hash`).
14. **`backend/app/schemas/auth.py`** — `SignupRequest` (field validators calling `normalize_phone`, trimming `name`,
    lowercasing `email`, `""` → `None`), `LoginRequest`, `AuthResponse` (`access_token: str`,
    `token_type: Literal["bearer"] = "bearer"`, `owner: OwnerRead`).
15. **`backend/app/core/deps.py`**
    - `_bearer = HTTPBearer(auto_error=False)` — **`auto_error=False` is required**: with the default, a missing header yields
      403, which breaks the 401 acceptance criterion (§11)
    - `get_current_owner(credentials = Depends(_bearer), db = Depends(get_db)) -> Owner` — raises
      `HTTPException(401, "not authenticated", headers={"WWW-Authenticate": "Bearer"})` per rule 10
    - `CurrentOwner = Annotated[Owner, Depends(get_current_owner)]` for reuse by F2+
16. **`backend/app/api/routes/auth.py`** — `router = APIRouter(prefix="/auth")` with the three routes, each with
    `response_model` and documented `responses={}`; `signup` is `status_code=201`; translate service exceptions to
    `HTTPException(409, …)`.
17. **`backend/app/main.py`** — register the router.
18. **`backend/tests/conftest.py`** — add:
    - autouse per-test `_clean_tables` fixture: `TRUNCATE <all Base.metadata.sorted_tables> RESTART IDENTITY CASCADE`
      after each test (needed because `_create_schema` is session-scoped and nothing currently removes rows)
    - `owner_payload` helper, `owner_factory(client)` → signs up via the API and returns `(payload, token, owner_json)`
    - `auth_headers(token)` / `authed_client` fixtures
19. **`backend/tests/test_auth.py`** — the tests in §10.
20. `uv run ruff check . && uv run ruff format . && uv run pytest`.

## 9. Mobile implementation plan

**Dependencies:** `npx expo install expo-secure-store` plus `npm i react-hook-form zod @hookform/resolvers`
(CLAUDE.md §5). `expo-secure-store` contains native code → **a new EAS development build is required** before this runs on
the phone; F0.2's progress note already flagged this rebuild for F1. The form libraries are JS-only.

**Files**

| Path | New? | Contents |
|---|---|---|
| `src/lib/auth-storage.ts` | new | `saveToken(t: string): Promise<void>`, `getToken(): Promise<string \| null>`, `clearToken(): Promise<void>` over `SecureStore.*ItemAsync` with key `pgrent.auth.token`; on web (`Platform.OS === 'web'`, where SecureStore is unavailable) fall back to `localStorage` so the dev web target doesn't crash; every call wrapped so a storage failure resolves to `null` rather than throwing |
| `src/lib/phone.ts` | new | `normalizePhone(raw: string): string \| null` — same rules as the backend (§6 rule 2), used for client-side validation and unit-tested |
| `src/lib/auth-schemas.ts` | new | zod schemas `loginSchema` ({ identifier, password: min 8 }), `signupSchema` ({ name: min 1, phone refined via `normalizePhone`, email optional, password: min 8 }) + inferred types |
| `src/types/auth.ts` | new | `Owner`, `AuthResponse`, `SignupBody`, `LoginBody` |
| `src/api/client.ts` | modify | accept an auth token: module-level `setAuthToken(t: string \| null)` (set by `AuthProvider`) and send `Authorization: Bearer <t>` when present; add `apiPost<T>(path, body)`; on non-2xx, read `{detail}` and pass it to `ApiError` as a new optional `detail` field (keep the existing `ApiError(status)` signature working — F0.2's tests construct it with status only) |
| `src/api/auth.ts` | new | `signup(body)`, `login(body)`, `fetchMe()` |
| `src/api/use-auth.ts` | new | `useMe()` (`queryKey: ['me']`, enabled only when a token exists), `useLogin()`, `useSignup()` — on success: store the token, `setAuthToken`, `queryClient.setQueryData(['me'], res.owner)`; `useLogout()` — clear token, `setAuthToken(null)`, `queryClient.clear()` |
| `src/components/auth-provider.tsx` | new | context `{ token, isHydrating, signIn(token), signOut() }`; hydrates from `getToken()` on mount |
| `src/app/_layout.tsx` | modify | `QueryClientProvider` → `AuthProvider` → `ThemeProvider` → gate: while `isHydrating` keep the splash overlay; no token → auth stack; token → `AppTabs` (see §12 Q6 on `Stack.Protected` vs conditional render) |
| `src/app/(auth)/_layout.tsx` | new | `Stack` with `headerShown: false` |
| `src/app/(auth)/login.tsx` | new | identifier + password fields, "Log in" button, link to Signup |
| `src/app/(auth)/signup.tsx` | new | name, phone, email (optional), password fields, "Create account" button, link to Login |
| `src/app/settings.tsx` | modify | new ACCOUNT card above BACKEND: owner name + phone from `useMe()`, and a Logout button |

**UX details**
- Inputs: phone → `keyboardType="phone-pad"`, `autoComplete="tel"`; email → `keyboardType="email-address"`,
  `autoCapitalize="none"`, `autoCorrect={false}`; password → `secureTextEntry`, `autoCapitalize="none"`, with a show/hide toggle;
  `returnKeyType="next"` chaining to the next field and `"go"` submitting the last.
- Buttons are full-width, ≥ 48 dp tall, using `Spacing.four` padding (CLAUDE.md §2 — large tap targets).
- Submit disabled while the mutation is pending; label changes to "Logging in…" / "Creating account…".
- Field-level validation errors render under each field in `theme.statusError`; the server's `detail` renders once above the
  button in the same colour (so a 401 shows "Invalid phone/email or password" verbatim).
- Network failure (no `detail`, e.g. the 5 s timeout) shows "Can't reach server. Check your connection." — same vocabulary as
  the existing `StatusPill`.
- Logout asks for confirmation with `Alert.alert('Log out?', …)` and only then clears the token.
- Screens are wrapped in `KeyboardAvoidingView` so the keyboard doesn't cover the button on a mid-range phone.
- Screens hold no logic beyond wiring: validation in `auth-schemas.ts`, storage in `auth-storage.ts`, requests in `src/api/`.

## 10. Test plan

### Backend (pytest) — `backend/tests/test_auth.py`

| Test name | Scenario | Expected result | AC IDs |
|---|---|---|---|
| `test_signup_success` | POST signup with name/phone/password | 201; `token_type == "bearer"`; non-empty `access_token`; `owner.phone == "+919876543210"` | AC-1 |
| `test_signup_creates_pg` | after signup, query `pgs` for the new owner | exactly one row; `name == "My PG"`; `address is None`; `default_rent_due_day == 5` | AC-2 |
| `test_signup_duplicate_phone` | sign up twice with the same phone | 409, `detail == "an account with this phone already exists"`; still one owner row | AC-3 |
| `test_signup_duplicate_phone_other_format` | sign up `+919876543210`, then `98765 43210` | 409 (same detail) | AC-4 |
| `test_signup_duplicate_email` | two signups, different phones, same email in different case | 409, `detail == "an account with this email already exists"` | AC-5 |
| `test_signup_normalises_phone` *(parametrised: `98765 43210`, `09876543210`, `919876543210`, `+91-98765-43210`)* | signup, then read the owner row | `owners.phone == "+919876543210"` in every case | AC-6 |
| `test_signup_invalid_phone` *(parametrised: `12345`, `0512345678`, `98765432100`, `abcdefghij`)* | signup with a bad phone | 422; no owner row created | AC-7 |
| `test_signup_short_password` | password `"short"` | 422 | AC-8 |
| `test_signup_blank_name` | `name = "   "` | 422 | AC-14 |
| `test_signup_without_email` | signup omitting `email`, and again with `email: ""` | 201 both times; `owners.email is None`; two accounts coexist with NULL email | AC-9 |
| `test_signup_hides_password_hash` | inspect the 201 body | no `password_hash` / `password` key anywhere in the JSON | AC-21 |
| `test_password_is_hashed_in_db` | read `owners.password_hash` | differs from the plaintext and starts with `$argon2` | AC-21 |
| `test_login_with_phone` | signup, then login with the phone | 200; valid `access_token`; `owner.id` matches | AC-10 |
| `test_login_with_email` | signup with an email, login with it (mixed case) | 200 | AC-11 |
| `test_login_with_unnormalised_phone` | signup `+919876543210`, login `98765 43210` | 200 | AC-12 |
| `test_login_wrong_password` | correct identifier, wrong password | 401, `detail == "invalid phone/email or password"` | AC-13 |
| `test_login_unknown_identifier_same_message` | login as a never-registered phone; compare to the wrong-password body | 401; byte-identical body to `test_login_wrong_password` | AC-14b |
| `test_login_malformed_identifier` | `identifier = "not-a-phone"` | 401 (**not** 422), same generic detail | AC-15 |
| `test_me_with_token` | GET `/auth/me` with the signup token | 200; `id`/`name`/`phone` match; no `password_hash` key | AC-16, AC-21 |
| `test_me_without_token` | GET `/auth/me`, no header | 401, `detail == "not authenticated"` | AC-17 |
| `test_me_with_malformed_token` *(parametrised: `"Bearer garbage"`, `"Basic abc"`, `"Bearer "`, token signed with a different secret)* | GET `/auth/me` | 401 in every case | AC-18 |
| `test_me_with_expired_token` | token built via `create_access_token(id, now=utcnow - 31 days)` | 401 | AC-19 |
| `test_me_with_unknown_owner_token` | token for a random UUID that has no owner row | 401 | AC-20 |
| `test_me_isolation_between_owners` | sign up owners A and B; call `/auth/me` with each token | each response returns only its own owner; A's token never yields B's id/phone/email | AC-22 |
| `test_pgs_due_day_check_constraint` | insert a `Pg` with `default_rent_due_day = 0` (and `29`) via the session | `IntegrityError` on flush | AC-23 |
| `test_phone_normalisation_unit` *(parametrised, no HTTP)* | call `normalize_phone` directly, valid + invalid inputs | returns E.164 / raises `ValueError` | AC-6, AC-7 |

### Mobile (Jest) — `mobile/__tests__/`

| Test name | Type | Scenario | Expected result | AC IDs |
|---|---|---|---|---|
| `normalize-phone.test.ts` | logic | the same valid/invalid table as the backend | E.164 string / `null` | AC-6 |
| `auth-schemas.test.ts` | logic | `loginSchema` / `signupSchema` against good and bad input | password < 8 and unparseable phone fail; valid input passes | AC-8, AC-7 |
| `auth-storage.test.ts` | logic | `jest.mock('expo-secure-store')`; save → get → clear | `getToken()` returns the saved token, then `null` after `clearToken()`; a throwing SecureStore yields `null` instead of crashing | AC-24, AC-26 |
| `client-auth-header.test.ts` | logic | `setAuthToken('abc')`, mock `fetch`, call `apiGet('/auth/me')` | request carries `Authorization: Bearer abc`; after `setAuthToken(null)` the header is absent | AC-27 |
| `api-error-detail.test.ts` | logic | mock `fetch` → 401 `{"detail":"invalid phone/email or password"}` | rejects with `ApiError`, `status === 401`, `detail` equal to the server string | AC-28 |
| `login-screen.test.tsx` | component | mock `login()` to reject with `ApiError(401, …)`, submit the form | the generic message is shown; `saveToken` not called (RNTL `render` is **async** under React 19 — `await` it, per F0.2's note) | AC-13, AC-28 |
| `auth-gate.test.tsx` | component | render the root gate with `getToken()` → `null`, then → `'tok'` | no token → Login screen; token → Dashboard | AC-24, AC-26 |

### Manual checklist (on the phone)

1. `cd backend && uv run alembic upgrade head` on a clean `pgrent_dev` → completes; `\d owners` and `\d pgs` in psql show the columns, unique constraints and the due-day check. *(AC-29)*
2. `uv run pytest` → all green; `uv run ruff check .` → clean. *(AC-29)*
3. `cd mobile && npx tsc --noEmit` → no errors; `npm test` → all green. *(AC-30)*
4. Rebuild the EAS development build (new native module `expo-secure-store`) and install it; `npx expo start --dev-client`. *(AC-24)*
5. Open the app with no account → the **Login** screen appears, not the tabs. *(AC-24)*
6. Tap "Sign up", enter name, `98765 43210`, no email, an 8-character password → account created and the app lands on **Dashboard**. *(AC-1, AC-6, AC-24)*
7. Go to **Settings** → the ACCOUNT card shows the name and `+919876543210`. *(AC-16, AC-6)*
8. **Kill the app from the recents list and reopen it** → it opens on Dashboard, still logged in, no login screen flash. *(AC-25)*
9. Settings → **Logout** → confirm → back at Login. Reopen the app → still Login. *(AC-26)*
10. Log in with `98765 43210` and the **wrong** password → "Invalid phone/email or password" appears above the button; no crash. *(AC-13, AC-28)*
11. Log in with the right password typed as `098765 43210` → Dashboard. *(AC-12)*
12. Try signing up again with the same number → the screen shows "An account with this phone already exists". *(AC-3)*
13. Stop the backend, try to log in → "Can't reach server" style message within ~5 s, no hang. *(AC-28)*

## 11. Edge cases and risks

- **`HTTPBearer` defaults to 403.** `fastapi.security.HTTPBearer(auto_error=True)` raises **403** when the header is missing,
  which fails AC-17. `auto_error=False` + an explicit 401 is mandatory, and the test asserts the status.
- **F0.1's conftest never deletes rows.** `_create_schema` is session-scoped with no truncation, so the second test to sign up
  with the same phone would hit `uq_owners_phone` and fail for the wrong reason. The autouse truncate fixture (§8 step 18) is
  part of this feature, not a nice-to-have.
- **Duplicate-signup race.** Two concurrent signups pass the pre-check and one hits `IntegrityError`; the service must catch it,
  roll back and map the constraint name to the right 409. Unlikely with one owner, trivial to get right now.
- **Login timing leak.** argon2 takes ~50–100 ms, so an early return for an unknown identifier is measurably faster than a wrong
  password. Verifying against `DUMMY_HASH` closes the obvious gap. No rate limiting in the MVP — worth revisiting if the app
  is ever public (CLAUDE.md §4 keeps auth minimal for now).
- **`JWT_SECRET` defaults to `"change-me"`** in `Settings`. Fine locally; in production this must be a real secret or anyone
  can forge tokens. Flagged for the deploy step, not changed here.
- **30-day tokens cannot be revoked.** Logout only deletes the token on the device; a copied token stays valid until `exp`.
  Acceptable for one owner; revocation would need a token version column or a denylist (out of scope).
- **Clock skew / expiry.** PyJWT validates `exp` against the server clock in UTC; `TIMESTAMPTZ` columns and UTC `iat`/`exp`
  keep this independent of the `TZ=Asia/Kolkata` display setting.
- **`+91` is assumed.** `normalize_phone` accepts Indian numbers only; a non-Indian number is a 422 at signup. Correct for the
  MVP, but it means the error message should say what's wrong rather than just "invalid".
- **Email uniqueness with NULLs.** Postgres permits unlimited NULLs under a unique constraint, so many owners can have no email
  — the `""` → `None` coercion in the schema is what keeps empty strings from colliding on the second signup.
- **Argon2 cost on free-tier hosting.** Default `PasswordHasher` parameters use ~64 MB of memory per hash; on a 512 MB free
  instance a burst of logins could be tight. One owner logging in rarely makes this a non-issue now; revisit if multi-tenant.
- **SecureStore is unavailable on web** and can throw on a device with a broken keystore; `auth-storage` must degrade to
  "no token" (→ Login screen) instead of crashing at startup.
- **Auth gate flicker.** Reading SecureStore is async, so without holding the splash overlay during `isHydrating` the app shows
  Login for a frame before jumping to Dashboard — exactly what manual step 8 checks.
- **Token present but rejected (expired after 30 days).** `useMe()` getting a 401 must clear the stored token and drop the owner
  back to Login, otherwise the app sits on a Dashboard that cannot load anything.
- **Stale npm installs.** F0.2 hit three silently broken `node_modules` installs; if Metro or Jest breaks right after adding
  `expo-secure-store` / `react-hook-form`, suspect the install before the code.

## 12. Blockers and open questions

No blockers: F0.1 and F0.2 are both complete, and nothing F1 needs is missing from the codebase.

| # | Question | Recommendation |
|---|---|---|
| Q1 | **FEATURES.md puts the `pgs` table in F2, but F1's own bullet says signup "creates owner **and** their PG (see F2)".** Which feature creates the table? | **Create `owners` + `pgs` in F1's single migration and auto-create the PG row at signup** (as specified above). Signup cannot insert a PG into a table that doesn't exist, and CLAUDE.md §9 wants one migration per schema-changing feature. F2 then adds no schema: it contributes `GET`/`PATCH /pg`, the 1–28 validation at the API layer, `get_current_pg`, and the Settings UI — and F2's "auto-creation on signup" test still passes. The alternative (F1 = `owners` only, no PG at signup) contradicts F1's text and would leave F2 having to backfill PGs for existing owners. |
| Q2 | Access-token lifetime, given the manual check "kill the app, reopen — still logged in". | **30 days** (`jwt_expires_minutes = 43200`), no refresh token. Long enough that the owner effectively never sees the login screen, short enough that a lost phone's token eventually dies. Configurable via env. |
| Q3 | Should `POST /auth/signup` and `/auth/login` return the owner alongside the token? | **Yes** — `AuthResponse.owner`. Saves a round trip on a phone on mobile data and lets the app render the Dashboard immediately; `/auth/me` remains the source of truth on later launches. |
| Q4 | Three new backend dependencies: `argon2-cffi`, `pyjwt`, `email-validator`. | **Accept all three.** CLAUDE.md §5 names argon2 and JWT. PyJWT over `python-jose` (maintained, far smaller); `argon2-cffi` directly rather than `passlib` (passlib's last release is 2020 and its bcrypt backend breaks on bcrypt 4.x); `email-validator` is what Pydantic's `EmailStr` needs. All free, no runtime cost. |
| Q5 | Hand-rolled `normalize_phone` vs the `phonenumbers` library. | **Hand-rolled** (~20 lines, fully unit-tested, mirrored in TS for the app). `phonenumbers` is a ~2 MB dependency for a single country. Revisit only if non-Indian numbers ever matter. |
| Q6 | Login identifier: one `identifier` field or separate `phone`/`email` fields? | **One `identifier` field.** FEATURES.md says "phone or email + password"; one field means one input on the phone and no "which did I use?" decision for the owner. |
| Q7 | How to gate navigation in Expo Router 58 — `Stack.Protected` / route guards vs conditionally rendering the navigator? | **Use `Stack.Protected` if expo-router 58 exposes it; otherwise conditionally render the auth `Stack` vs `AppTabs` from the root layout.** Verify on the device during step 5 — this interacts with `NativeTabs`, which F0.2 already found to be the less-travelled path. |
| Q8 | *(Suggestion for later, not F1)* Should `Settings` show the token's expiry or a "logged in as" timestamp? | Skip. Not asked for, and it adds nothing for the owner. |

## 13. Changelog

- 2026-10-20: Spec created — `owners` + `pgs` tables, argon2 + JWT auth, three `/auth` endpoints, `get_current_owner`,
  phone normalisation, mobile auth screens with `expo-secure-store`, and 30 acceptance criteria.

## 14. Acceptance criteria

- **AC-1:** `POST /api/v1/auth/signup` with a valid name, phone and password returns **201** with a non-empty `access_token`, `token_type: "bearer"` and the created owner. _(Source: FEATURES.md · Verified by: `test_signup_success`, Manual step 6)_
- **AC-2:** Signup also creates exactly one PG for that owner, named "My PG" with `default_rent_due_day = 5`. _(Source: FEATURES.md F1/F2 · Verified by: `test_signup_creates_pg`)_
- **AC-3:** Signup with an existing phone returns **409** and does not create a second account. _(Source: FEATURES.md · Verified by: `test_signup_duplicate_phone`, Manual step 12)_
- **AC-4:** A phone already registered in another format (`+919876543210` vs `98765 43210`) is still rejected with **409**. _(Source: Spec §6 rule 3 · Verified by: `test_signup_duplicate_phone_other_format`)_
- **AC-5:** Signup with an already-registered email (any letter case) returns **409**. _(Source: Spec §6 rule 4, §7 · Verified by: `test_signup_duplicate_email`)_
- **AC-6:** Phones are stored in E.164: `98765 43210`, `09876543210`, `919876543210` and `+91-98765-43210` all persist as `+919876543210`. _(Source: FEATURES.md, CLAUDE.md §7 · Verified by: `test_signup_normalises_phone`, `test_phone_normalisation_unit`, `normalize-phone.test.ts`, Manual steps 6–7)_
- **AC-7:** Signup with an unparseable phone returns **422** and creates no owner. _(Source: Spec §6 rule 2, §7 · Verified by: `test_signup_invalid_phone`, `test_phone_normalisation_unit`, `auth-schemas.test.ts`)_
- **AC-8:** Signup with a password shorter than 8 characters returns **422**. _(Source: Spec §6 rule 6 · Verified by: `test_signup_short_password`, `auth-schemas.test.ts`)_
- **AC-9:** Email is optional: signup without `email` (or with `""`) succeeds and stores `NULL`, and several such accounts can coexist. _(Source: FEATURES.md · Verified by: `test_signup_without_email`)_
- **AC-10:** `POST /api/v1/auth/login` with the registered phone and correct password returns **200** with a token. _(Source: FEATURES.md · Verified by: `test_login_with_phone`, Manual step 11)_
- **AC-11:** Login with the registered email and correct password returns **200** with a token. _(Source: FEATURES.md · Verified by: `test_login_with_email`)_
- **AC-12:** Login accepts the phone in any supported format, not just E.164. _(Source: Spec §6 rules 2, 7 · Verified by: `test_login_with_unnormalised_phone`, Manual step 11)_
- **AC-13:** A wrong password returns **401** with the generic detail `invalid phone/email or password`. _(Source: FEATURES.md · Verified by: `test_login_wrong_password`, `login-screen.test.tsx`, Manual step 10)_
- **AC-14:** A blank or whitespace-only `name` on signup returns **422**. _(Source: Spec §6 rule 14 · Verified by: `test_signup_blank_name`)_
- **AC-14b:** An unknown identifier returns **401** with a body identical to the wrong-password response, so responses never reveal whether an account exists. _(Source: FEATURES.md ("generic message"), Spec §6 rule 8 · Verified by: `test_login_unknown_identifier_same_message`)_
- **AC-15:** An identifier that is neither a valid phone nor an email returns **401**, not 422. _(Source: Spec §6 rule 8 · Verified by: `test_login_malformed_identifier`)_
- **AC-16:** `GET /api/v1/auth/me` with a valid token returns **200** with the caller's own `id`, `name`, `phone`, `email` and `created_at`. _(Source: FEATURES.md · Verified by: `test_me_with_token`, Manual step 7)_
- **AC-17:** `GET /api/v1/auth/me` without an `Authorization` header returns **401** (not 403). _(Source: FEATURES.md, Spec §11 · Verified by: `test_me_without_token`)_
- **AC-18:** A malformed token, a non-Bearer scheme, or a token signed with another secret returns **401**. _(Source: Spec §6 rule 10, §7 · Verified by: `test_me_with_malformed_token`)_
- **AC-19:** An expired token returns **401**. _(Source: Spec §6 rules 9, 10 · Verified by: `test_me_with_expired_token`)_
- **AC-20:** A well-formed token whose owner no longer exists returns **401**. _(Source: Spec §6 rule 10, §11 · Verified by: `test_me_with_unknown_owner_token`)_
- **AC-21:** No response body contains `password_hash` or the password, and the stored hash is an argon2 hash, never the plaintext. _(Source: CLAUDE.md §9, Spec §6 rules 6, 12 · Verified by: `test_signup_hides_password_hash`, `test_password_is_hashed_in_db`, `test_me_with_token`)_
- **AC-22:** With two accounts registered, each token returns only its own owner — owner A's token never yields owner B's data. _(Source: CLAUDE.md §7 · Verified by: `test_me_isolation_between_owners`)_
- **AC-23:** A PG row with `default_rent_due_day` outside 1–28 cannot be stored. _(Source: CLAUDE.md §7, Spec §5 · Verified by: `test_pgs_due_day_check_constraint`)_
- **AC-24:** After signup or login on the phone, the token is saved in `expo-secure-store` and the app shows the Dashboard; with no stored token it shows the Login screen. _(Source: FEATURES.md · Verified by: `auth-storage.test.ts`, `auth-gate.test.tsx`, Manual steps 4–6)_
- **AC-25:** Killing the app and reopening it keeps the owner logged in — the Dashboard appears without re-entering the password. _(Source: FEATURES.md Manual check · Verified by: Manual step 8)_
- **AC-26:** Logout in Settings clears the stored token and returns to the Login screen, and reopening the app still shows Login. _(Source: FEATURES.md · Verified by: `auth-storage.test.ts`, `auth-gate.test.tsx`, Manual step 9)_
- **AC-27:** Requests to protected endpoints carry `Authorization: Bearer <token>`, and no header is sent once the token is cleared. _(Source: CLAUDE.md §8, Spec §9 · Verified by: `client-auth-header.test.ts`)_
- **AC-28:** The server's error `detail` is shown to the owner on a failed login, and an unreachable server produces a "can't reach server" message within ~5 s instead of hanging. _(Source: Spec §9, §11 · Verified by: `api-error-detail.test.ts`, `login-screen.test.tsx`, Manual steps 10, 13)_
- **AC-29:** `alembic upgrade head` on an empty database creates `owners` and `pgs` with their unique and check constraints, and `uv run pytest` plus `uv run ruff check .` pass. _(Source: CLAUDE.md §5, §9, §10 · Verified by: Manual steps 1–2)_
- **AC-30:** `npx tsc --noEmit` reports no errors under `strict`, and `npm test` passes. _(Source: CLAUDE.md §9 · Verified by: Manual step 3)_
