# CLAUDE.md — PG Rent Tracker

This file tells Claude Code what we are building, how the project is organised, and how to work on it.
Read this file fully before writing any code. The feature-by-feature plan lives in `FEATURES.md`.

---

## 1. What we are building

A mobile app that helps a **PG (paying guest) owner** in India replace the paper diary they use to track rent.

Today the owner writes down, by hand, which tenant paid rent for which month. Chasing unpaid rent means
scrolling through the diary, then calling or WhatsApp-ing each tenant one by one.

The app lets the owner:

1. Keep a list of tenants (name, phone, room/bed, rent, deposit, join date, etc.).
2. See, for each month, who has **paid**, who has **partially paid**, and who is **pending / overdue**.
3. Record a payment (cash / UPI / bank) in one or two taps.
4. Send a rent reminder over **WhatsApp** to one tenant, or go through all pending tenants quickly.
5. **Call** a tenant directly from the app.
6. See a tenant's full payment history.

A new month's rent entries are created automatically for every active tenant.

## 2. Who uses it

- **Primary user: the PG owner.** Not very tech-savvy, uses an Android phone, often in a hurry.
  The UI must be simple, large-tap-target, minimal typing, and fast on a mid-range phone.
- **Tenants do NOT use the app** in this phase. They only receive WhatsApp messages/calls from the owner's phone.

## 3. Project goals and stage

- This is a **learning project first**. The first real user is one PG owner (the developer's own PG owner).
- If he uses it for 1–2 months and likes it, we may onboard more PGs and turn it into a business.
- So: build for **one owner with one PG**, but design the data model so **multiple owners and multiple PGs**
  can be supported later **without a rewrite** (every PG-owned row carries `pg_id`; every PG belongs to an owner).
- Keep running costs at ~₹0/month: free tiers, no paid APIs.

## 4. Scope

### In scope (MVP)
- Owner account (simple email/phone + password login).
- One PG per owner (auto-created on signup, editable name/address).
- Rooms and beds.
- Tenants: add, edit, list, search, move-out.
- Monthly rent records generated automatically.
- Record payments (full or partial), payment methods, payment history.
- Monthly dashboard: paid / partial / pending / overdue + totals collected vs due.
- WhatsApp reminders via `wa.me` deep links (single tenant + guided "go through all pending" flow).
- Call via `tel:` links.
- Simple reminder log.

### Out of scope for now (do NOT build unless a feature in FEATURES.md asks for it)
- Online payment collection (Razorpay / UPI gateway).
- WhatsApp Business API / automatic server-sent messages.
- SMS OTP login.
- Tenant-facing app or tenant login.
- KYC document uploads.
- Multiple PGs per owner in the UI (the DB supports it; the UI does not yet).
- Electricity bill splitting, food/mess management, complaints.

## 5. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, **FastAPI** |
| ORM / migrations | **SQLAlchemy 2.x** (typed models) + **Alembic** |
| Validation | **Pydantic v2** |
| Database | **PostgreSQL** — local dev uses the machine's installed **PostgreSQL 18** (NOT Docker), hosted on Neon/Supabase free tier in prod |
| Python env | Managed by **uv**, pinned to **Python 3.12** (`backend/.python-version`); `uv.lock` committed, `.venv/` gitignored |
| DB driver | **psycopg3** — connection URLs use `postgresql+psycopg://…` (a bare `postgresql://` would select psycopg2) |
| Auth | Password hashing with `argon2` (or `bcrypt`), **JWT** access tokens |
| Scheduled jobs | Idempotent "generate month" service, triggered by APScheduler **and** lazily on dashboard load |
| Backend tests | **pytest** + FastAPI `TestClient`/`httpx`, separate test database |
| Mobile app | **React Native + Expo**, **TypeScript**, **Expo Router** |
| Data fetching | **TanStack Query** |
| Forms | `react-hook-form` + `zod` |
| Token storage | `expo-secure-store` |
| Mobile tests | **Jest** + React Native Testing Library (for logic and key components) |
| Hosting | Render / Railway / Fly.io free tier for API, Neon for Postgres |

If a library choice is unclear, prefer the simplest well-maintained option and say why.

**Local database (important):** dev and test run against the machine's local PostgreSQL 18 on
`localhost:5432`, not Docker. Databases: `pgrent_dev` (dev) and `pgrent_test` (pytest wipes this one).
Role `pgrent` / password `pgrent` (the name avoids Postgres's reserved `pg_` prefix).
Connection strings live in `backend/.env` (see `backend/.env.example`).
Do **not** create `docker-compose.yml` or run `docker compose` for the DB. Two rules keep local and prod in sync:
1. **All schema changes go through Alembic migrations — never hand-edit tables in pgAdmin/psql.** Browsing data and running `SELECT`s is fine.
2. **Do not use Postgres-18-only features** (e.g. `uuidv7()`); the host may run an older major version. Plain tables, indexes, constraints and FKs work on any recent version.
If you ever run a Docker Postgres alongside the local one, map it to port **5433** (both can't use 5432).

## 6. Repository layout

```
pg-rent-app/
├── CLAUDE.md
├── FEATURES.md
├── backend/
│   ├── pyproject.toml
│   ├── .python-version         # pins Python 3.12 for uv
│   ├── .env.example            # DATABASE_URL, TEST_DATABASE_URL, JWT_SECRET, TZ
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py             # FastAPI app factory, router registration
│   │   ├── core/               # config (pydantic-settings), security (hashing, JWT), deps
│   │   ├── db/                 # engine, session, Base
│   │   ├── models/             # SQLAlchemy models, one file per entity
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── api/routes/         # one router per resource (auth, pg, rooms, tenants, rent, payments, reminders)
│   │   ├── services/           # business logic (rent generation, status calc, message templates)
│   │   └── jobs/               # scheduler setup
│   └── tests/
│       ├── conftest.py         # test DB, client, authenticated-owner fixtures
│       └── test_<feature>.py
└── mobile/                     # Expo SDK 58, React 19.3, RN 0.88, TypeScript strict
    ├── app.json
    ├── .env.example            # EXPO_PUBLIC_API_URL (LAN IP on a real phone)
    ├── jest.config.js          # jest-expo preset
    ├── src/
    │   ├── app/                # Expo Router screens (NOTE: under src/, not mobile/app/)
    │   │   ├── _layout.tsx     # root: QueryClientProvider + AuthProvider + Stack with Stack.Protected
    │   │   ├── (auth)/         # _layout.tsx, login.tsx, signup.tsx — shown when there is no token
    │   │   └── (tabs)/         # _layout.tsx renders AppTabs; the signed-in area
    │   │       ├── index.tsx   # Dashboard tab
    │   │       └── tenants.tsx · rooms.tsx · settings.tsx
    │   ├── api/                # API client (reads EXPO_PUBLIC_API_URL) + TanStack Query hooks
    │   ├── components/         # ThemedText/ThemedView, app-tabs, status-pill, placeholders
    │   ├── constants/          # theme: Colors, Spacing, status tokens
    │   ├── hooks/              # use-theme, use-color-scheme
    │   ├── lib/                # helpers: config, health mapping, money/phone/wa.me (later)
    │   └── types/
    └── __tests__/
```
Routing lives in **`mobile/src/app/`** (the installed scaffold's layout; `@/*` → `./src/*`), not `mobile/app/`.

The four tabs sit in a **`(tabs)/` group** rather than at the root, because `NativeTabs` resolves each
trigger's `name` against its own layout's siblings and redirects away from any focused route no visible
trigger declares — an `(auth)` route alongside the tabs would be bounced back to the first tab. The root
`_layout.tsx` is therefore a `Stack` with two `Stack.Protected` groups: `(tabs)` guarded by having a token,
`(auth)` guarded by not having one. Group names are navigator structure, not URL segments, so the public
paths stay `/`, `/tenants`, `/rooms`, `/settings`. Adding or moving a route changes the generated
`Href` union in `.expo/types/router.d.ts` (typed routes are on), which only regenerates when Metro boots —
run `npx expo start` once before `npx tsc --noEmit` or a new path will not typecheck.

## 7. Data model

All tables have `id` (UUID), `created_at`, `updated_at`. Every PG-owned table has `pg_id` (FK → `pgs.id`)
and **every query must be scoped to the logged-in owner's PG**. Never return another owner's data.
**UUIDs are generated in Python (`uuid.uuid4()`), never by a DB function** like `uuidv7()`, so the schema
stays portable across Postgres versions and hosts (see §5, local-database rule 2).

**owners** — `name`, `phone` (unique, E.164), `email` (nullable, unique), `password_hash`.

**pgs** — `owner_id` (FK), `name`, `address`, `default_rent_due_day` (1–28, default 5).

**rooms** — `pg_id`, `room_number` (unique per PG), `floor` (nullable), `capacity` (number of beds), `notes`.

**tenants** — `pg_id`, `room_id` (FK, nullable), `bed_label` (nullable, e.g. "A"),
`full_name`, `phone` (E.164), `alt_phone` / emergency contact (nullable), `email` (nullable),
`monthly_rent` (integer, paise), `security_deposit` (integer, paise), `rent_due_day` (1–28),
`join_date`, `leave_date` (nullable), `status` (`active` | `notice` | `left`), `notes`.

**rent_records** — one row per tenant per month.
`pg_id`, `tenant_id`, `period` (date = first day of month, e.g. `2026-11-01`), `amount_due` (paise),
`amount_paid` (paise, denormalised sum of payments), `due_date`, `status` (`pending` | `partial` | `paid`).
**Unique constraint on (`tenant_id`, `period`)** — this is what makes monthly generation idempotent.

**payments** — `pg_id`, `rent_record_id`, `tenant_id`, `amount` (paise, > 0), `paid_on` (date),
`method` (`cash` | `upi` | `bank` | `other`), `reference` (nullable, e.g. UPI txn id), `notes`.

**reminder_logs** — `pg_id`, `tenant_id`, `rent_record_id` (nullable), `channel` (`whatsapp` | `call`), `sent_at`.

### Business rules
- **Money is stored as integers in paise.** Never use floats for money. Format as `₹12,500` in the UI.
- **Timezone is `Asia/Kolkata`.** "Today", month boundaries and overdue checks use IST.
- **Status** is derived from amounts: `paid` if `amount_paid >= amount_due`, `partial` if `0 < amount_paid < amount_due`, else `pending`.
- **Overdue** is not stored. A record is overdue when status ≠ `paid` and today (IST) > `due_date`.
- **Monthly generation**: for a given month, create a `rent_record` for every tenant who is `active` or `notice`
  and whose `join_date` is on or before the last day of that month and who has not left before the month starts.
  `amount_due` = tenant's `monthly_rent`; `due_date` = that month's `rent_due_day`.
  Must be **idempotent** (running twice creates nothing new). No pro-rating in the MVP.
- Changing a tenant's `monthly_rent` affects only **future** months, never existing rent records.
- Payments can be edited/deleted; `amount_paid` and `status` on the rent record must be recalculated in the same transaction.
- **Phone numbers** are normalised to E.164 (`+91XXXXXXXXXX`) on save. Accept inputs like `98765 43210`, `09876543210`, `+91-98765-43210`.

### WhatsApp and calls
- Reminders use `https://wa.me/<digits-without-plus>?text=<url-encoded message>`, opened on the owner's phone.
  No WhatsApp API, no server-side sending.
- `wa.me` **cannot bulk-send**. "Remind all" is a guided flow: open WhatsApp for tenant 1, owner sends,
  comes back, taps "Next" for tenant 2, and so on.
- Calls use `tel:+91XXXXXXXXXX`.
- Message templates live in one place (backend `services/messages.py`, mirrored or fetched by the app) and include
  tenant name, month, amount pending, PG name. English first; keep strings ready for Hindi/Kannada later.

## 8. API conventions
- Prefix: `/api/v1`. JSON only. Auth via `Authorization: Bearer <token>`.
- Resource-style routes (`GET /tenants`, `POST /tenants`, `PATCH /tenants/{id}`).
- Errors: proper HTTP codes with `{"detail": "..."}`. 404 (not 403) when a resource belongs to another PG.
- List endpoints support simple filters/search via query params; paginate only when needed.
- Every route has a Pydantic request and response schema. No raw dicts.

## 9. Coding conventions
- Backend: type hints everywhere, `ruff` for lint + format, business logic in `services/`, routes stay thin.
- One Alembic migration per feature that changes the schema. Never edit an applied migration.
- Mobile: TypeScript strict mode, functional components, no business logic in screens (put it in `src/lib` or hooks).
- Secrets and DB URLs only via environment variables (`.env`, never committed). Provide `.env.example`.
- Keep the UI simple: big buttons, clear colours for status (green = paid, amber = partial, red = overdue, grey = pending not yet due).

## 10. How to work on this project (important)

We build **one feature at a time**, in the order in `FEATURES.md`.

For each feature:
1. Read the feature's section in `FEATURES.md` (goal, acceptance criteria, tests).
2. Implement **only that feature**. Do not start the next feature or add things "for later".
3. Backend first: model/migration → service → route → **pytest tests covering every acceptance criterion**.
4. Then the mobile screen(s) for that feature, plus Jest tests for any helper logic.
5. Run all tests (`pytest`, `npm test`) and lint. Everything must pass.
6. Give a short manual test checklist for the developer to try on the phone.
7. Mark the feature's checkbox in `FEATURES.md` as done and note anything deferred.

If a feature needs a schema change not described here, or the spec is ambiguous, **stop and ask** rather than guessing.

## 11. Common commands

```bash
# Local database: PostgreSQL 18 already runs as a system service on localhost:5432 — no Docker.
# One-time setup (run as the postgres superuser), creates the role and both databases:
#   sudo -u postgres psql -c "CREATE USER pgrent WITH PASSWORD 'pgrent';"
#   sudo -u postgres psql -c "CREATE DATABASE pgrent_dev OWNER pgrent;"
#   sudo -u postgres psql -c "CREATE DATABASE pgrent_test OWNER pgrent;"

# Backend
cd backend
uv sync                                   # creates .venv (Python 3.12) and installs deps
cp .env.example .env                      # first time only
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format .

# Mobile
cd mobile
npm install
npx expo start                            # open in Expo Go on the phone
npm test
```

The mobile app reads the API base URL from `EXPO_PUBLIC_API_URL`. When testing on a real phone,
use the laptop's LAN IP (not `localhost`).