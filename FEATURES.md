# FEATURES.md — PG Rent Tracker: feature-by-feature build plan

Build these **in order, one at a time**. Each feature should be fully working and tested before starting the next.
See `CLAUDE.md` for the data model, business rules and conventions.

Every feature has:
- **Goal** — what it does for the owner.
- **Backend / Mobile** — what to build.
- **Acceptance criteria** — what must be true when it's done.
- **Tests** — automated tests to write (backend: pytest; mobile: Jest where there's logic).
- **Manual check** — what to try on the phone.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Phase 0 — Foundations

### [x] F0.1 Backend skeleton
Spec: specs/F0.1-backend-skeleton.md
**Goal:** A running FastAPI app connected to Postgres with migrations and tests set up.
**Backend:**
- Project layout from `CLAUDE.md`, `pyproject.toml`, `ruff` config.
- `docker-compose.yml` with Postgres. `.env.example` with `DATABASE_URL`, `JWT_SECRET`, `TZ=Asia/Kolkata`.
- Settings via `pydantic-settings`, SQLAlchemy engine/session, Alembic initialised.
- `GET /api/v1/health` returns `{"status": "ok"}` and checks DB connectivity.
- `tests/conftest.py`: separate test database, tables created/dropped per test session, a `client` fixture.

**Acceptance criteria:**
- `alembic upgrade head` runs on an empty DB.
- `GET /api/v1/health` returns 200 with DB up.
- `pytest` passes.

**Tests:** health endpoint returns 200 and expected body.

### [x] F0.2 Mobile skeleton
Spec: specs/F0.2-mobile-skeleton.md
**Goal:** An Expo app that runs on the owner's phone and talks to the backend.
**Mobile:**
- Expo + TypeScript + Expo Router. Tabs: Dashboard, Tenants, Rooms, Settings (placeholders).
- API client reading `EXPO_PUBLIC_API_URL`, TanStack Query provider.
- Settings screen shows API health status.
- Jest configured.

**Acceptance criteria:** App opens in Expo Go on a phone; Settings shows "Connected" when the backend is running and "Can't reach server" when it isn't.
**Tests:** a trivial component render test so Jest is proven to work.
**Manual check:** open the app on your phone over LAN; stop the backend and confirm the error state.

---

## Phase 1 — Owner account and PG

### [~] F1 Owner signup and login
Spec: specs/F1-owner-signup-and-login.md
**Goal:** The owner can create an account and log in; all data is private to them.
**Backend:**
- `owners` table + migration.
- `POST /auth/signup` (name, phone, optional email, password) → creates owner **and** their PG (see F2), returns token.
- `POST /auth/login` (phone or email + password) → JWT.
- `GET /auth/me` → current owner.
- Password hashing; JWT dependency `get_current_owner`.

**Acceptance criteria:**
- Signup with an existing phone returns 409.
- Wrong password returns 401 with a generic message.
- Protected routes return 401 without a valid token.
- Phone stored in E.164.

**Tests:** signup success; duplicate phone; login success; login wrong password; `/auth/me` with and without token; phone normalisation (`98765 43210` → `+919876543210`).
**Mobile:** Login and Signup screens; token in `expo-secure-store`; redirect to Dashboard when logged in; Logout in Settings.
**Manual check:** sign up, kill the app, reopen — still logged in; log out — back at login.

### [ ] F2 PG profile
**Goal:** The owner has one PG with a name, address and default rent due day.
**Backend:**
- `pgs` table + migration. A PG is auto-created at signup (name defaults to "My PG").
- `GET /pg` and `PATCH /pg` (name, address, default_rent_due_day 1–28).
- A `get_current_pg` dependency used by all later routes.

**Acceptance criteria:** due day outside 1–28 rejected (422); owner A cannot read or change owner B's PG.
**Tests:** auto-creation on signup; get; update; validation; isolation between two owners.
**Mobile:** PG details section in Settings, editable.

---

## Phase 2 — Rooms and tenants

### [ ] F3 Rooms
**Goal:** The owner can list the PG's rooms and how many beds each has.
**Backend:** `rooms` table + migration. CRUD: `GET/POST /rooms`, `PATCH/DELETE /rooms/{id}`.
`GET /rooms` returns each room with `capacity` and `occupied` (count of active/notice tenants).
**Acceptance criteria:**
- Room number unique within a PG (409 on duplicate); same number allowed in different PGs.
- Cannot delete a room with active tenants (409).
- Capacity must be ≥ 1.

**Tests:** CRUD; duplicate number; delete blocked when occupied; occupancy count; cross-PG isolation.
**Mobile:** Rooms tab: list with "2/3 beds filled", add/edit room form.

### [ ] F4 Add and edit tenants
**Goal:** Replace the diary's tenant list.
**Backend:** `tenants` table + migration. `POST /tenants`, `GET /tenants/{id}`, `PATCH /tenants/{id}`.
Fields per `CLAUDE.md`. `rent_due_day` defaults to the PG's `default_rent_due_day`. Money accepted from the app in rupees and stored as paise (decide one convention and document it in the schema).
**Acceptance criteria:**
- Required: full name, phone, monthly rent, join date.
- Phone normalised to E.164; invalid phone rejected.
- Assigning a tenant to a full room is rejected (409).
- Room must belong to the same PG.

**Tests:** create with defaults; validation errors; room-full rule; room from another PG rejected; update fields; isolation.
**Mobile:** Add Tenant form (minimal required fields first, optional fields collapsed under "More details"); Edit Tenant screen.
Phone field with numeric keypad. Rent field formatted as ₹.

### [ ] F5 Tenant list and search
**Goal:** Find any tenant quickly.
**Backend:** `GET /tenants?status=active|notice|left&room_id=&q=` — `q` matches name, phone or room number. Default: active + notice.
**Acceptance criteria:** search is case-insensitive and works on partial name/phone; results sorted by room number then name.
**Tests:** filter by status; search by name / phone / room; default filter excludes `left`.
**Mobile:** Tenants tab: search bar, list rows showing name, room/bed, rent; tap to open tenant detail; floating "+" to add.

### [ ] F6 Notice and move-out
**Goal:** Handle tenants leaving.
**Backend:** `POST /tenants/{id}/notice` (expected leave date) → status `notice`; `POST /tenants/{id}/move-out` (leave date) → status `left`, bed freed.
**Acceptance criteria:**
- Leave date cannot be before join date.
- A `left` tenant gets no rent records for months starting after their leave date.
- Their old rent records and payments remain visible.

**Tests:** status transitions; bed freed (occupancy drops); date validation; history preserved.
**Mobile:** "Give notice" and "Mark as left" actions on tenant detail, with a confirm dialog.

---

## Phase 3 — Rent tracking (the core)

### [ ] F7 Monthly rent generation
**Goal:** Each month, every current tenant automatically gets a rent entry — the owner never creates them by hand.
**Backend:**
- `rent_records` table + migration with unique (`tenant_id`, `period`).
- `services/rent.py: generate_month(pg_id, period)` following the rules in `CLAUDE.md`. Idempotent.
- Triggered by: (a) APScheduler daily job at ~00:30 IST for the current month, (b) lazily whenever the dashboard for a month is requested, (c) when a new tenant is added (create the current month's record).
- `POST /rent/generate?period=YYYY-MM` for manual runs.

**Acceptance criteria:**
- Running twice creates no duplicates.
- Tenants who left before the month, or join after it, get no record.
- `amount_due` uses the tenant's rent at generation time; later rent changes don't alter existing records.
- `due_date` uses the tenant's due day in that month.

**Tests:** these cases with fixed dates (use a frozen clock, e.g. `time-machine`): normal; idempotent; joined mid-month; joined next month; left last month; on notice; rent change after generation; Feb with due day 28.
**Mobile:** nothing visible yet (feeds F9).

### [ ] F8 Record a payment
**Goal:** Mark rent as paid in a couple of taps — full or partial.
**Backend:**
- `payments` table + migration.
- `POST /rent-records/{id}/payments` (amount, paid_on defaults to today IST, method, reference, notes).
- `PATCH /payments/{id}`, `DELETE /payments/{id}`.
- Recompute `amount_paid` and `status` on the rent record in the same transaction.

**Acceptance criteria:**
- Amount must be > 0.
- Paying the full due → `paid`; less → `partial`; deleting the payment → back to `pending`.
- Overpayment allowed but flagged in the response (`overpaid_by`), not silently lost.

**Tests:** full; partial then remaining; edit amount; delete; overpayment; payment on another PG's record → 404.
**Mobile:** "Mark paid" bottom sheet: amount prefilled with the pending amount, method chips (Cash / UPI / Bank / Other), optional reference, Save. Undo toast after saving.

### [ ] F9 Monthly dashboard
**Goal:** One screen that answers "who has paid this month and who hasn't?"
**Backend:** `GET /dashboard?period=YYYY-MM` (default current month) returns:
- totals: `due`, `collected`, `pending`, counts of paid / partial / pending / overdue.
- rows: tenant name, phone, room/bed, amount due, amount paid, status, `is_overdue`, due date.

**Acceptance criteria:**
- Generates the month lazily if missing (F7).
- Overdue computed in IST.
- Sorted: overdue first, then partial, pending, paid.

**Tests:** totals correct with mixed statuses; overdue flag around the due date boundary (frozen clock); empty PG; previous month view.
**Mobile:** Dashboard tab: month switcher (‹ Oct 2026 ›), summary cards (Collected ₹X of ₹Y), filter chips (All / Pending / Overdue / Paid), colour-coded list. Tap a row → Mark paid (F8). Pull to refresh.
**Manual check:** add 3 tenants, pay one fully, one partially, leave one — check the counts and colours.

### [ ] F10 Tenant payment history
**Goal:** Settle "I already paid for August" arguments.
**Backend:** `GET /tenants/{id}/rent-history` — all rent records, newest first, each with its payments.
**Acceptance criteria:** includes months with no payment; totals of all-time due/paid/outstanding.
**Tests:** history order; outstanding total across months; left tenant still has history.
**Mobile:** history section on Tenant Detail: month, due, paid, status; expand a month to see individual payments.

---

## Phase 4 — Reminders and calls

### [ ] F11 Call a tenant
**Goal:** Call directly from the app.
**Mobile:** Call button on dashboard rows and tenant detail → `tel:+91...`.
**Backend:** `POST /reminders` with channel `call` creates a `reminder_logs` row (table + migration added here).
**Tests:** backend log creation; mobile helper `buildTelLink(phone)` unit-tested.
**Manual check:** tapping Call opens the dialer with the right number.

### [ ] F12 WhatsApp reminder to one tenant
**Goal:** Send a ready-made rent reminder on WhatsApp in one tap.
**Backend:**
- `services/messages.py`: `rent_reminder(tenant, record, pg)` → text, e.g.
  "Hi Rahul, this is a reminder that rent of ₹8,500 for October 2026 at Sri Sai PG is pending. Please pay at the earliest. Thank you."
  Uses pending amount (due − paid), not full rent.
- `GET /rent-records/{id}/reminder-message` returns the text.
- Log via `POST /reminders` with channel `whatsapp`.

**Acceptance criteria:** message shows the correct pending amount and month; Indian number formatting (₹12,500).
**Tests:** message for pending vs partial; formatting; log creation.
**Mobile:** helper `buildWhatsAppLink(phone, text)` → `https://wa.me/91XXXXXXXXXX?text=...` (unit-tested with spaces, emoji, special characters). WhatsApp button on dashboard rows and tenant detail; show "Reminded 2 days ago" from the log.
**Manual check:** WhatsApp opens on the right chat with the message filled in.

### [ ] F13 Remind all pending (guided flow)
**Goal:** Chase everyone who hasn't paid without scrolling and tapping each row.
**Backend:** `GET /dashboard/reminder-queue?period=YYYY-MM&only_overdue=false` → ordered list of unpaid records with their messages.
**Mobile:** "Remind all (N)" button on the dashboard opens a step-through screen: shows tenant 1 → "Open WhatsApp" → owner sends and returns → "Next" → tenant 2 … with "Skip" and progress (3/8). Each opened chat is logged.
**Acceptance criteria:** paid tenants never appear; tenants already reminded today are marked so the owner can skip them.
**Tests:** queue excludes paid; overdue-only filter; order matches dashboard.
**Manual check:** run the flow end to end for 3 tenants.

---

## Phase 5 — Polish for the real owner (after he has used Phases 1–4)

Pick these based on his feedback; reorder freely.

### [ ] F14 Payment receipt
Generate a simple receipt (PG name, tenant, month, amount, method, date, receipt no.) and share it as text or image via WhatsApp.

### [ ] F15 Deposit tracking
Record deposit received, deductions and refund on move-out; show deposits held in Settings.

### [ ] F16 Export
Export a month or a tenant's history as CSV / PDF so the owner can keep a backup or show his accountant.

### [ ] F17 Local language
Hindi and Kannada (and/or Marathi) for UI strings and reminder messages; per-owner language setting.

### [ ] F18 Onboarding import
Quickly add many tenants at once (simple multi-row form or CSV paste) so moving off the diary takes minutes.

---

## Later — only if it becomes a business

- Multiple PGs per owner in the UI (DB already supports it).
- Phone OTP login.
- UPI payment link / QR with automatic "paid" marking (Razorpay or UPI deep links).
- WhatsApp Business API for automatic reminders on the due date.
- Tenant app (view dues, download receipts).
- KYC / ID document storage.
- Subscription billing for PG owners.

---

## Progress notes

Record anything deferred, changed or learned while building each feature here.

| Feature | Date | Notes |
|---|---|---|
| F1 (backend) | 2026-10-20 | **Backend half done — 66 pytest tests pass, ruff clean, `alembic check` reports no model/migration drift. Mobile half still to do, so the feature stays `[~]`.** Endpoints: `POST /auth/signup` (201), `POST /auth/login`, `GET /auth/me`, plus `get_current_owner` / `CurrentOwner` in `app/core/deps.py` for F2+. **Decisions:** (1) F1 creates **both** `owners` and `pgs` in one migration (`0002_owners_and_pgs`) and signup inserts the owner + their "My PG" row in one transaction — FEATURES.md lists `pgs` under F2, but F1's own bullet requires the PG at signup, so **F2 now has no schema change** (only `GET`/`PATCH /pg`, the 1–28 API validation, `get_current_pg`, Settings UI). (2) Token lifetime **30 days**, no refresh token. (3) `AuthResponse` includes the owner, to save the app a round trip. (4) Login takes a single `identifier` field (phone or email). (5) Hand-rolled `normalize_phone` rather than the `phonenumbers` dependency. **Added beyond the spec:** a `naming_convention` on `Base.metadata` (done now, while there were zero tables) so constraints are `pk_owners` / `uq_owners_phone` / `ck_pgs_default_rent_due_day_range` / `fk_pgs_owner_id_owners` / `ix_pgs_owner_id` — `signup_owner` reads `IntegrityError.orig.diag.constraint_name` to tell a duplicate phone from a duplicate email, which needs stable names. **Two spec corrections found in the installed libraries:** FastAPI 0.150's `HTTPBearer(auto_error=True)` returns **401**, not the 403 the spec assumed (old behaviour) — `auto_error=False` is still right, but for detail consistency; and `HTTPBearer` **does not check the scheme**, handing over credentials for `Basic …` too, so `get_current_owner` rejects a non-bearer scheme itself. **Gotchas:** PyJWT 2.15 warns that an HS256 secret under 32 bytes is too short — the `JWT_SECRET` placeholder was 23 bytes, so `.env.example` now carries a 32+ byte placeholder and a `secrets.token_urlsafe` generator line. `tests/conftest.py` had no row cleanup (F0.1's `_create_schema` is session-scoped), so an autouse fixture now truncates **on entry, not exit** — truncating in teardown can block on the transaction a finished test still holds. Postgres was simply not running after a reboot (`sudo systemctl start postgresql@18-main`); "Connection refused" is a down server, not a bad password. **Minor deviations from the spec:** `RegisteredOwner.headers` replaces the separate `auth_headers` / `authed_client` fixtures, and `test_phone_normalisation_unit` is split into valid/invalid cases. **Deferred to the mobile pass:** screens, `expo-secure-store`, auth gate, Logout, 7 Jest tests. Key finding: an `(auth)` group **cannot** sit under the current `NativeTabs` root layout — `useVisibleTabsWithRedirect` `router.replace()`s any focused route no visible trigger declares, and `hidden: true` "cannot be navigated to in any way". So move `index/rooms/tenants/settings` into `src/app/(tabs)/` with its own `_layout.tsx` rendering `<AppTabs />`, and make the root `_layout.tsx` a `<Stack>` with two `Stack.Protected` groups (it does exist in expo-router 58.0.24; `NativeTabs` has no equivalent). `expo-secure-store`, `react-hook-form`, `@hookform/resolvers` and a resolvable `zod` are all **not installed**; typed routes (`.expo/types/router.d.ts`) must be regenerated before `/login` typechecks; and a **new EAS dev build** is needed for the native module. |
| F0.2 | 2026-10-20 | **Done — verified on a real phone (Realme 5 Pro) via an EAS development build.** All six device ACs pass: four tabs + placeholders, Settings **Connected**, red **Can't reach server** (API stopped), amber **Server up, database down** (503). Automated: `tsc --noEmit` clean, `npm test` 6/6. Decisions: kept the scaffold's **`src/app/`** routing (CLAUDE.md §6 updated); **three-way health state** — 503 gets its own state via a typed `ApiError` carrying the HTTP status (AC-3b); `expo-secure-store` deferred to F1; tab icons via `sf`+`md`. **Expo Go could not be used** — it only supports the SDK its store build ships, and this project is SDK 58; so we moved to an EAS dev build (`eas.json` development profile + `expo-dev-client`, pkg `com.pgrent.tracker`, EAS project `@tejaskumbhar288/pg-rent-tracker`). Day-to-day: `npx expo start --dev-client`. **Three broken npm installs had to be repaired** (files silently missing from `node_modules`): `hermes-parser` (no `dist/generated/`) blocked Metro *and* Jest; `@expo-google-fonts/material-symbols` (no `.ttf`) broke the bundle once `md` icons were used; plus a junk `2g` dir (the real `2g` is a legit `@expo/cli` dep). Watch for this pattern. Gotchas: RNTL v14 `render` is **async** under React 19 (tests must `await`, needs the `test-renderer` peer); Jest maps `@/*` and stubs `*.css`; `tsconfig` pins `types:["jest"]`; `npx eas` resolves an unrelated squatter package — use `eas-cli`. Next native rebuild needed at **F1** (`expo-secure-store`). |
| F0.1 | 2026-10-20 | Done. **Local PostgreSQL 18, no Docker** (role `pgrent`, DBs `pgrent_dev`/`pgrent_test` — `pg_rent` rejected: Postgres reserves `pg_` prefix). uv-managed venv, Python 3.12. Health endpoint returns 503 on DB-down (beyond spec's 200-only). CLAUDE.md §5/§6/§7/§11 updated to match. 3 pytest tests pass, ruff clean. Benign Starlette `httpx` deprecation warning in TestClient — left as-is. |