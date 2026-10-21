# F2 — PG profile

| | |
|---|---|
| Phase | Phase 1 — Owner account and PG |
| Status | Draft |
| Depends on | F0.1 ✅ · F0.2 ✅ · F1 ⚠️ partial (backend merged and tested; mobile code merged but the on-device checklist is still open, so F1 is `[~]`. Nothing F2 needs is missing.) |
| Used by | F3 (rooms), F4 (tenants — inherits `default_rent_due_day`), F7 (rent generation), F9 (dashboard), F12 (reminder messages use the PG name) — every PG-scoped route depends on `get_current_pg` |
| Last updated | 2026-10-21 |

## 1. Summary

The owner's PG already exists — F1 creates it at signup — but nothing can read or change it. F2 makes it a real
profile: the owner can see and edit the PG's **name**, **address** and **default rent due day** from Settings.
The name is what later appears in WhatsApp reminders ("…at Sri Sai PG"), and the default due day is the value
every new tenant's own `rent_due_day` is copied from. F2 also adds `get_current_pg`, the dependency that gives
every later feature its PG scope in one place.

## 2. User stories

- As a PG owner, I want to replace "My PG" with my PG's real name, so that rent reminders I send look like they came from my PG and not from an app.
- As a PG owner, I want to record my PG's address, so that it is in one place when I need it.
- As a PG owner, I want to set the day of the month rent is due, so that I don't have to set it on every tenant I add.
- As a PG owner, I want my PG's details to be mine alone, so that no other owner can read or change them.

## 3. Scope

**In scope:**
- `GET /api/v1/pg` — the authenticated owner's PG.
- `PATCH /api/v1/pg` — partial update of `name`, `address`, `default_rent_due_day`.
- `default_rent_due_day` validated as an integer 1–28 at the API layer (422), on top of F1's DB check constraint.
- `get_current_pg` / `CurrentPg` in `app/core/deps.py`, plus `app/services/pg.py`.
- `apiPatch` in the mobile API client (the first PATCH in the app).
- A **PG DETAILS** card in Settings with an inline edit mode.

**Out of scope:**
- Any schema change or Alembic migration — `pgs` shipped in F1's `0002_owners_and_pgs` (§5).
- Creating or deleting a PG from the app, and therefore `POST /pg`. Signup is the only thing that creates one; nothing deletes one (§12 Q2).
- Multiple PGs in the UI (CLAUDE.md §4) — no PG switcher, no `pg_id` in any request.
- Rooms, beds, tenants, rent (F3+).
- A PG logo or photo, currency setting, per-PG language (F17), owner profile editing (name/phone/email stay read-only).
- Applying a changed due day retroactively to existing tenants or rent records (§6 rule 9).

## 4. Current state of the codebase

| What exists | Where | Note for F2 |
|---|---|---|
| `Pg` model — `owner_id`, `name`, `address`, `default_rent_due_day`, `id`, timestamps, `ck_pgs_default_rent_due_day_range` | `backend/app/models/pg.py` | Complete. F2 does **not** change it. |
| `pgs` + `owners` tables | `backend/alembic/versions/0002_owners_and_pgs.py` | Already applied. No new migration in F2. |
| PG auto-created at signup ("My PG", due day 5) | `backend/app/services/auth.py` — `signup_owner`, `DEFAULT_PG_NAME`, `DEFAULT_RENT_DUE_DAY` | The two constants move to `services/pg.py` (§8 step 2). |
| `get_current_owner` / `CurrentOwner`, 401 `not authenticated` | `backend/app/core/deps.py` | `get_current_pg` is built on top of it. Its closing comment already says so. |
| Route pattern: thin routes, `APIRouter(prefix=...)`, `responses={...}` examples, service does the work | `backend/app/api/routes/auth.py` | Follow it exactly. |
| Schema pattern: explicit fields, `_trim` and `_blank_is_absent` `mode="before"` validators | `backend/app/schemas/auth.py`, `schemas/owner.py` | Reuse both validator shapes for `name` and `address`. |
| Deterministic constraint names | `backend/app/db/base.py` — `NAMING_CONVENTION` | Nothing to add. |
| Test fixtures: `client`, `db`, `owner_payload`, `owner_factory` → `RegisteredOwner.headers`, autouse `TRUNCATE` | `backend/tests/conftest.py` | `owner_factory(phone=...)` twice gives the two owners the isolation test needs. |
| `ApiError`, `apiGet`, `apiPost`, `setAuthToken` (5 s timeout, `detail` extraction) | `mobile/src/api/client.ts` | **No `apiPatch` yet** — F2 adds it. |
| `useMe` pattern: `enabled: token !== null`, `retry: false`, 401 → `signOut()` | `mobile/src/api/use-auth.ts` | `usePg` copies the `enabled`/`retry` shape. |
| Settings screen with an ACCOUNT card and a BACKEND card | `mobile/src/app/(tabs)/settings.tsx` | The PG card goes between them. |
| `FormField` (label + inline error, 48 dp), `PrimaryButton`, `describeApiError`, `confirmAction`, `Spacing`/`Colors` | `mobile/src/components/`, `mobile/src/lib/`, `mobile/src/constants/theme.ts` | All reused as-is; no new components beyond the card. |
| Form pattern: `react-hook-form` + `Controller` + `zodResolver` | `mobile/src/app/(auth)/signup.tsx`, `mobile/src/lib/auth-schemas.ts` | Follow it. Note the transform caveat in §9. |

## 5. Data model changes

**None.** The `pgs` table, its FK, its index and the 1–28 check constraint all shipped in F1's
`0002_owners_and_pgs` migration, because signup inserts an owner and their PG in one transaction
(recorded as F1 spec Q1 and in FEATURES.md's progress notes).

F2 therefore adds **no Alembic migration**. `uv run alembic check` must report no drift at the end (AC-21);
if it reports any, a model was changed by accident and that change needs its own migration (CLAUDE.md §5 rule 1).

For reference, the columns F2 reads and writes:

| Column | Type | Nullable | Default | F2 |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid.uuid4()` in Python | read-only |
| `owner_id` | `UUID` FK → `owners.id` `ON DELETE CASCADE`, indexed | no | — | never exposed, never writable |
| `name` | `VARCHAR(120)` | no | `"My PG"` (Python-side) | read + write |
| `address` | `TEXT` | yes | `NULL` | read + write (clearable) |
| `default_rent_due_day` | `SMALLINT`, `CHECK BETWEEN 1 AND 28` | no | `5` | read + write |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | no | `now()`, `updated_at` bumped `onupdate` | `created_at` read-only; `updated_at` not exposed |

## 6. Business rules

1. **One PG per owner in the UI.** The PG is created at signup (F1) and F2 never creates or deletes one. The schema still allows several rows per owner so multi-PG can land later without a rewrite (CLAUDE.md §3).
2. **The PG is resolved from the token, never from the request.** There is no `pg_id` path parameter or body field. This is what makes cross-owner access impossible rather than merely checked (CLAUDE.md §7).
3. `get_current_pg` returns the owner's PG, selected as `ORDER BY pgs.created_at, pgs.id LIMIT 1`. The `id` tie-break matters: two rows created in one transaction share the same `created_at`, so without it the "current" PG would not be stable between requests.
4. If the authenticated owner has **no** PG row, PG routes return **404** with `detail: "pg not found"` — never an auto-created PG (§12 Q2). The app presents that one status as an empty state ("No PG set up yet."), not as a raw error line, and F2 gives the owner no way to create a PG from the app.
5. **`name`** is trimmed before saving, must be 1–120 characters after trimming, and is never null. Blank, whitespace-only, `null` or over-long → 422.
6. **`address`** is optional free text. It is **trimmed** before saving (so the 500-character cap is measured after trimming); `""` or whitespace-only is stored as `NULL`, and an explicit `null` clears it. Capped at 500 characters at the API layer (§12 Q5) although the column is `TEXT`.
7. **`default_rent_due_day`** is an integer **1–28** (CLAUDE.md §7). A non-numeric string, a fractional number, a boolean and an explicit `null` are all rejected → 422. A JSON string or float that represents a whole number in range (`"7"`, `9.0`) is **accepted** and stored as that integer: Pydantic v2's standard lax coercion, deliberately kept so a non-app client sending `9.0` is not punished. What is stored is always a validated integer in 1–28, which is the property that matters. The upper bound is 28 so that the due day exists in every month — February has no 29th in most years, and the MVP does no clamping.
8. **PATCH is partial.** Only the fields present in the body change; omitted fields are left exactly as they were. An empty body `{}` is a valid no-op that returns the unchanged PG (§12 Q7). The service applies `payload.model_dump(exclude_unset=True)` — **`exclude_unset`, not `exclude_none`**, because `address: null` must be distinguishable from "address not mentioned".
9. **Changing `default_rent_due_day` is forward-looking only.** It is the value copied into a new tenant's `tenants.rent_due_day` when the tenant is created (F4). Existing tenants keep their own `rent_due_day`, and rent records already generated keep their `due_date` (F7). This mirrors CLAUDE.md §7's rule that a rent change affects only future months.
10. A successful PATCH advances `pgs.updated_at` (the `Timestamps` mixin's `onupdate`).
11. **Responses never include `owner_id`.** Fields are listed explicitly in `PgRead` the same way `OwnerRead` avoids ever emitting `password_hash`.
12. Both routes require a valid bearer token; without one they return **401** `not authenticated`, reusing F1's `get_current_owner` (CLAUDE.md §8).
13. The database check constraint stays as the backstop: a `default_rent_due_day` outside 1–28 cannot be stored even if it bypassed the API layer (already covered by F1's `test_pgs_due_day_check_constraint`).
14. No money, phone or timezone handling in F2 — the PG profile holds none of those.

## 7. API contract

All paths under `/api/v1` (CLAUDE.md §8). JSON only. `Authorization: Bearer <token>` required on both.

### `GET /api/v1/pg` — **auth required**

No request body.

Response **200** (`PgRead`):

```json
{
  "id": "9b1f0c2a-4e77-4a51-9f3d-0b6a1c8e2d44",
  "name": "Sri Sai PG",
  "address": "12, 4th Cross, Koramangala, Bengaluru 560034",
  "default_rent_due_day": 5,
  "created_at": "2026-10-20T09:15:00+05:30"
}
```

Straight after signup, before any edit: `name` is `"My PG"`, `address` is `null`, `default_rent_due_day` is `5`.

Errors:

| Status | `detail` | When |
|---|---|---|
| 401 | `not authenticated` | no header, wrong scheme, malformed / expired / foreign-signed token, owner row gone |
| 404 | `pg not found` | the authenticated owner has no PG row (rule 4) |

### `PATCH /api/v1/pg` — **auth required**

Request (`PgUpdate`) — every field optional, partial update:

| Field | Type | Validation |
|---|---|---|
| `name` | `str` | trimmed; 1–120 chars after trimming; not nullable |
| `address` | `str \| None` | trimmed; `""`/whitespace → `None`; max 500 chars; explicit `null` clears it |
| `default_rent_due_day` | `int` | `ge=1`, `le=28`; must be an integer (`5.5`, `"abc"`, `null` → 422) |

Example request:

```json
{ "name": "  Sri Sai PG  ", "default_rent_due_day": 10 }
```

Response **200**: the full updated PG, same body shape as `GET` (here `name` saved as `"Sri Sai PG"`,
`default_rent_due_day` `10`, `address` untouched).

Errors:

| Status | `detail` | When |
|---|---|---|
| 401 | `not authenticated` | as above |
| 404 | `pg not found` | as above |
| 422 | FastAPI validation body | blank/null/over-long `name`, address over 500 chars, due day outside 1–28, fractional, non-numeric, boolean or `null` |

**PG scoping.** Neither route takes an identifier, so owner A has nothing to point at owner B's PG with —
the 404-for-another-owner's-resource convention (CLAUDE.md §8) has no path parameter to bite on here and
first applies in F3 (`/rooms/{id}`). The guarantee F2 must prove is the one in rule 2: each token resolves
only to its own owner's PG, and A's PATCH leaves B's row untouched (AC-12).

## 8. Backend implementation plan

In order:

1. **`backend/app/services/pg.py`** (new) — all PG business logic; the route stays thin (CLAUDE.md §9).
   - `DEFAULT_PG_NAME = "My PG"` and `DEFAULT_RENT_DUE_DAY = 5`, moved here from `services/auth.py` (this is the PG's module now).
   - `get_pg_for_owner(db: Session, owner_id: uuid.UUID) -> Pg | None` — `select(Pg).where(Pg.owner_id == owner_id).order_by(Pg.created_at, Pg.id).limit(1)`, per rule 3.
   - `update_pg(db: Session, pg: Pg, changes: Mapping[str, Any]) -> Pg` — `setattr` each key, `db.commit()`, `db.refresh(pg)`, return it. An empty `changes` commits nothing and returns `pg` unchanged (rule 8).
2. **`backend/app/services/auth.py`** — import `DEFAULT_PG_NAME` / `DEFAULT_RENT_DUE_DAY` from `app.services.pg` and delete the local definitions. No behaviour change; F1's `test_signup_creates_pg` must still pass untouched.
3. **`backend/app/schemas/pg.py`** (new):
   - `PgRead` — `model_config = ConfigDict(from_attributes=True)`; `id: uuid.UUID`, `name: str`, `address: str | None`, `default_rent_due_day: int`, `created_at: datetime`. Fields listed explicitly (rule 11), mirroring `OwnerRead`.
   - `PgUpdate` — `name: Annotated[str, Field(min_length=1, max_length=120)] | None = None`, `address: Annotated[str, Field(max_length=500)] | None = None`, `default_rent_due_day: Annotated[int, Field(ge=1, le=28)] | None = None`, with `_trim` (`mode="before"`, on `name`) and `_blank_is_absent` (`mode="before"`, on `address`) copied from `schemas/auth.py`.
   - **Note:** `None` doubles as the "absent" marker for `name` and `default_rent_due_day`, but an explicit `null` for those two must be a **422**, not a silent no-op. Add a `@model_validator(mode="before")` that rejects a key present with a `null` value for those two fields. `address` keeps `null` as a legitimate clear.
4. **`backend/app/core/deps.py`** — add below `CurrentOwner`:
   - `_pg_not_found() -> HTTPException` returning 404 `detail="pg not found"`, matching `_unauthenticated()`'s shape and lowercase wording.
   - `get_current_pg(owner: CurrentOwner, db: Annotated[Session, Depends(get_db)]) -> Pg` — calls `get_pg_for_owner`, raises `_pg_not_found()` on `None`.
   - `CurrentPg = Annotated[Pg, Depends(get_current_pg)]` — the dependency F3+ use for PG scoping.
5. **`backend/app/api/routes/pg.py`** (new) — `router = APIRouter(prefix="/pg")`, both routes registered on the **empty** path (`@router.get("")`, `@router.patch("")`) so no trailing-slash redirect is introduced.
   - `get_pg(pg: CurrentPg) -> PgRead` — `return PgRead.model_validate(pg)`.
   - `update_pg_details(payload: PgUpdate, pg: CurrentPg, db: Annotated[Session, Depends(get_db)]) -> PgRead` — `pg_service.update_pg(db, pg, payload.model_dump(exclude_unset=True))`, then `PgRead.model_validate(...)`.
   - `_UNAUTHENTICATED_RESPONSE` / `_PG_NOT_FOUND_RESPONSE` documentation dicts in the module, following `routes/auth.py`.
6. **`backend/app/main.py`** — `app.include_router(pg.router, prefix="/api/v1", tags=["pg"])` after the auth router.
7. **`backend/tests/conftest.py`** — add `PG_PATH = f"{API}/pg"` beside the existing path constants.
8. **`backend/tests/test_pg.py`** (new) — the table in §10.
9. **Gates:** `uv run alembic check` (expect no drift — F2 adds no migration), `uv run pytest`, `uv run ruff check . && uv run ruff format .`.

## 9. Mobile implementation plan

In order:

1. **`mobile/src/types/pg.ts`** (new) — `Pg` (`id`, `name`, `address: string | null`, `default_rent_due_day: number`, `created_at`) and `PgUpdateBody` (all three optional, `address?: string | null`).
2. **`mobile/src/api/client.ts`** — add `apiPatch<T>(path, body, opts?)`, identical in shape to `apiPost` but `method: 'PATCH'`. It inherits the bearer header, the 5 s abort and `ApiError` + `detail` extraction for free.
3. **`mobile/src/api/pg.ts`** (new) — `fetchPg(): Promise<Pg>` → `apiGet('/pg')`; `updatePg(body: PgUpdateBody): Promise<Pg>` → `apiPatch('/pg', body)`.
4. **`mobile/src/api/use-pg.ts`** (new):
   - `usePg()` — `useQuery({ queryKey: ['pg'], queryFn: fetchPg, enabled: token !== null, retry: false, staleTime: 5 * 60 * 1000 })`. `enabled` matters: without it the query fires on the login screen and 401s.
   - `useUpdatePg()` — `useMutation({ mutationFn: updatePg, onSuccess: (data) => queryClient.setQueryData(['pg'], data) })`. The response is the complete PG, so `setQueryData` is enough — no refetch round trip on mobile data.
5. **`mobile/src/lib/pg-schemas.ts`** (new) — `pgSchema`, messages phrased for the owner:
   - `name: z.string().trim().min(1, 'Enter a name for your PG').max(120, 'That name is too long')`
   - `address: z.string().max(500, 'That address is too long')` (`''` allowed, sent as `null`)
   - `dueDay: z.string().trim().refine(v => /^\d{1,2}$/.test(v) && Number(v) >= 1 && Number(v) <= 28, 'Enter a day from 1 to 28')`
   - **`dueDay` stays a string in the schema.** A `z.transform` to `number` would make zod's input and output types differ, which `react-hook-form` + `@hookform/resolvers@3` only handle via a three-generic `useForm`; converting with `Number(values.dueDay)` at submit time avoids that entirely.
   - Export `type PgValues = z.infer<typeof pgSchema>`.
6. **`mobile/src/components/pg-details-card.tsx`** (new) — the whole feature's UI, so `settings.tsx` stays a layout file (CLAUDE.md §9: no business logic in screens).
   - **View mode:** `PG DETAILS` label; name; address, or "No address yet" in `textSecondary`; "Rent due on the 5th of each month"; an **Edit** button styled like the existing `styles.retry` pressable.
   - **Edit mode:** `FormField`s for `PG NAME` (`autoCapitalize="words"`), `ADDRESS (OPTIONAL)` (`multiline`, with a `minHeight` in the style), `RENT DUE DAY` (`keyboardType="number-pad"`, `maxLength={2}`) with the hint "1–28, so it works in February too"; `PrimaryButton` "Save changes" / `pendingLabel="Saving…"`; a **Cancel** pressable that resets the form and returns to view mode.
   - `defaultValues` come from `usePg().data`; `reset()` is called when that data arrives or changes, so entering edit mode never shows a stale or empty form.
   - On submit: `updatePg.mutate({ name, address: address === '' ? null : address, default_rent_due_day: Number(dueDay) })`, and leave edit mode in `onSuccess`.
   - **Loading:** "Loading…" in `textSecondary`, matching the ACCOUNT card. **Error:** `describeApiError(query.error)` / `describeApiError(updatePg.error)` in `theme.statusError`; a failed save stays in edit mode with the typed values intact.
   - **No PG (404):** when `usePg` fails with `ApiError.status === 404`, the card reads "No PG set up yet." with "Please contact support." beneath it in `textSecondary`, and shows **no Edit button**. This case must be checked *before* falling back to `describeApiError`, which would otherwise render the API's lowercase `pg not found` as "Pg not found" — technically accurate and useless to the owner. Every other failure keeps the generic error line. No Create button in F2 (§12 Q2).
   - No `confirmAction` — editing your own PG name is not destructive.
7. **`mobile/src/app/(tabs)/settings.tsx`** — render `<PgDetailsCard />` between the ACCOUNT and BACKEND cards. No other change; no routing change, so `.expo/types/router.d.ts` does not need regenerating.
8. **Tests** — the four files in §10.
9. **Gates:** `npx tsc --noEmit`, `npm test`.

## 10. Test plan

### Backend (pytest) — `backend/tests/test_pg.py`

No date logic in F2, so no frozen clock is needed (`time-machine` still waits for F7). The only time assertion
is the `updated_at` ordering, which compares two reads of the same row.

| Test name | Scenario | Expected result | AC IDs |
|---|---|---|---|
| `test_get_pg_returns_signup_defaults` | sign up, then `GET /pg` | 200; `name == "My PG"`; `address is None`; `default_rent_due_day == 5`; `id` is a UUID | AC-1 |
| `test_get_pg_without_token` | `GET /pg`, no header | 401, `detail == "not authenticated"` | AC-11 |
| `test_get_pg_with_malformed_token` *(parametrised: `"Bearer garbage"`, `"Basic abc"`)* | `GET /pg` | 401 in both cases | AC-11 |
| `test_update_pg_all_fields` | PATCH name + address + due day, then `GET /pg` | 200; response carries the new values; the GET returns the same, so they persisted | AC-2 |
| `test_update_pg_partial_leaves_other_fields` | PATCH `{"name": "Sri Sai PG"}` only | 200; `address` and `default_rent_due_day` unchanged from their pre-PATCH values | AC-3 |
| `test_update_pg_clears_address` *(parametrised: `None`, `""`, `"   "`)* | set an address, then PATCH it away | 200; `address is None` in the response and in the DB row | AC-4 |
| `test_update_pg_trims_name` | PATCH `{"name": "  Sri Sai PG  "}` | 200; stored and returned as `"Sri Sai PG"` | AC-5 |
| `test_update_pg_rejects_bad_name` *(parametrised: `""`, `"   "`, `None`, 121 chars)* | PATCH a bad name | 422; the PG row is unchanged | AC-6 |
| `test_update_pg_rejects_long_address` | PATCH a 501-character address | 422; row unchanged | AC-7 |
| `test_update_pg_rejects_due_day_out_of_range` *(parametrised: `0`, `29`, `-1`, `100`)* | PATCH a due day outside 1–28 | 422; `default_rent_due_day` unchanged | AC-8 |
| `test_update_pg_rejects_non_integer_due_day` *(parametrised: `"abc"`, `5.5`, `None`, `True`)* | PATCH a non-integer due day | 422; row unchanged | AC-8 |
| `test_update_pg_accepts_boundary_due_days` *(parametrised: `1`, `28`)* | PATCH the boundary values | 200; the value is stored | AC-9 |
| `test_update_pg_empty_body_is_noop` | PATCH `{}` | 200; every field identical to before | AC-10 |
| `test_update_pg_without_token` | PATCH with a valid body, no header | 401, `detail == "not authenticated"`; row unchanged | AC-11 |
| `test_pg_isolation_between_owners` | sign up A and B (different phones); A PATCHes name + due day; GET as each | A sees A's new values; **B still sees `"My PG"` / `5`**; the two `id`s differ | AC-12 |
| `test_pg_response_omits_owner_id` | inspect the `GET` and `PATCH` bodies | no `owner_id` (and no `updated_at`) key in either | AC-13 |
| `test_update_pg_keeps_id_and_created_at` | PATCH, compare to the pre-PATCH `GET` | `id` and `created_at` unchanged | AC-13 |
| `test_pg_routes_404_when_owner_has_no_pg` | delete the owner's `Pg` row via the session, then `GET` and `PATCH` | 404, `detail == "pg not found"` on both | AC-14 |
| `test_update_pg_bumps_updated_at` | read `updated_at`, PATCH the name, re-read the row | `updated_at` is later than before and later than `created_at` | AC-15 |
| *(existing)* `test_pgs_due_day_check_constraint` in `tests/test_auth.py` | insert a `Pg` with due day `0` / `29` directly | `IntegrityError` on flush — the DB backstop still holds | AC-22 |
| *(existing)* `test_signup_creates_pg` in `tests/test_auth.py` | after the constants move to `services/pg.py` | still passes unchanged | AC-1 |

### Mobile (Jest) — `mobile/__tests__/`

| Test file | Type | Scenario | Expected result | AC IDs |
|---|---|---|---|---|
| `pg-schemas.test.ts` | logic | `pgSchema` against good and bad input: names (`''`, `'   '`, 121 chars, `'  Sri Sai PG  '`), addresses (`''`, 501 chars), due days (`'0'`, `'29'`, `'abc'`, `''`, `'1'`, `'28'`, `'10'`) | the bad cases fail with the owner-facing message; `'1'`, `'28'`, `'10'` pass; a blank address passes | AC-5, AC-6, AC-7, AC-8, AC-9 |
| `client-patch.test.ts` | logic | `setAuthToken('abc')`, mock `fetch`, call `apiPatch('/pg', {...})`; then a 422 response | the request uses `method: 'PATCH'`, `Content-Type: application/json`, `Authorization: Bearer abc` and the JSON body; a 422 rejects with `ApiError` carrying `status` and the server `detail` | AC-18 |
| `pg-details-card.test.tsx` | component | mock `usePg` four ways — loaded PG, `isLoading`, `isError` with a generic failure, and `isError` with `ApiError(404, 'pg not found')` — then press **Edit** on the loaded one. **No submit in this file** | view mode shows the name, address and due day; loading shows "Loading…"; a generic failure shows the mapped message; the 404 shows "No PG set up yet." and **no Edit button**; Edit reveals the three fields prefilled from the query data | AC-16, AC-20, AC-23 |
| `use-update-pg.test.tsx` | logic | mock `fetch`, call `useUpdatePg().mutate({...})` in a `QueryClientProvider` (`gcTime: 0` on mutations, per F1's note), await success | `PATCH /pg` is sent with the mapped body (`address: null` for a cleared address, numeric `default_rent_due_day`), and `queryClient.getQueryData(['pg'])` holds the server's response | AC-17 |

**Why the submit test lives in `use-update-pg.test.tsx` and not in the card test:** F1 found that RNTL 14 + React 19
leaves an `act()` scope open past a `react-hook-form` submit, so a second `render()` in the same file returns an empty
tree. The card file therefore stays render-only, and the submit path is covered one level down at the hook — the same
resolution F1 recorded for `login-screen.test.tsx`.

### Manual checklist (on the phone)

No new native module in F2, so the **existing EAS development build still works** — `npx expo start --dev-client`.

1. `cd backend && uv run alembic check` → "No new upgrade operations detected"; `uv run pytest` → all green; `uv run ruff check .` → clean. *(AC-19, AC-21)*
2. `cd mobile && npx tsc --noEmit` → no errors; `npm test` → all green. *(AC-19)*
3. Open the app logged in → **Settings** shows a **PG DETAILS** card: "My PG", "No address yet", "Rent due on the 5th of each month". *(AC-1, AC-16)*
4. Tap **Edit** → the three fields appear, prefilled with "My PG", empty address and `5`. *(AC-16)*
5. Change the name to "Sri Sai PG", type an address, set the due day to `10`, tap **Save changes** → the card returns to view mode showing all three new values, with no manual refresh. *(AC-2, AC-16, AC-17)*
6. Kill the app from recents, reopen, go to Settings → the new values are still there (they came from the server). *(AC-2)*
7. Edit → due day `0` → "Enter a day from 1 to 28" under the field and nothing is saved. Repeat with `30` and with `abc`. *(AC-8)*
8. Edit → clear the name → "Enter a name for your PG"; Save does nothing. *(AC-6)*
9. Edit → clear the address → Save → the card shows "No address yet" again. *(AC-4)*
10. Edit → due day `1`, Save; then `28`, Save → both accepted. *(AC-9)*
11. Stop the backend, open Settings again → the PG card shows a "Can't reach server" style message within ~5 s (the ACCOUNT and BACKEND cards still render). Try a Save → an error line appears, the typed values are still in the fields, no crash. *(AC-20)*
12. In psql, `SELECT name, address, default_rent_due_day FROM pgs;` → one row, matching what the phone shows. *(AC-2)*
13. *(destructive — on `pgrent_dev` only)* `DELETE FROM pgs;` in psql, then reopen Settings → the card reads "No PG set up yet. / Please contact support." with no Edit button and no crash. Sign up a fresh owner to get a PG back. *(AC-14, AC-23)*

## 11. Edge cases and risks

- **No migration is the expected outcome.** If `alembic check` reports drift, a model changed by accident — fix the model or give the change its own migration; never hand-edit the table (CLAUDE.md §5 rule 1).
- **`address: null` vs absent.** Using `exclude_none` instead of `exclude_unset` in the PATCH service would make the address impossible to clear, and the bug would be invisible until an owner tried it. The parametrised clear test pins this.
- **Explicit `null` for `name` / `default_rent_due_day`.** Because "absent" is also modelled as `None`, a body of `{"name": null}` would silently become a no-op without the §8 step 3 guard. Both are in the 422 parametrisations.
- **Pydantic coerces `True` to `1`.** `default_rent_due_day: true` would pass `ge=1, le=28` as `1` unless booleans are rejected; the non-integer test includes `True` so this is settled explicitly rather than by accident.
- **Due day 29–31 is deliberately impossible.** The owner may well want "last day of the month"; the MVP cannot express it, and the field hint explains the 28 limit rather than leaving the rejection unexplained — the same lesson F1 recorded about the phone error message.
- **Changing the due day will not move this month's rent.** The owner may expect it to. F2 only owns the default for future tenants (rule 9); F7/F9 are where a visible due date comes from. Worth saying out loud during the manual pass, while there are no tenants yet to make it concrete.
- **`get_current_pg` shape changes under multi-PG.** Today it resolves the single PG from the token; when multiple PGs per owner reach the UI, routes must pass a PG id and this dependency becomes "validate that this PG belongs to me". Every later feature depends on it, so the signature change is the cost — acceptable, and the reason the lookup lives in one function.
- **Two devices editing at once.** Last write wins; no optimistic locking or `If-Match`. Fine for one owner on one phone.
- **`usePg` firing while logged out.** Without `enabled: token !== null` the query runs on the login screen, 401s, and (unlike `useMe`) has no 401 handler — it would just show an error. The `enabled` guard is not optional.
- **A 401 from the PG query** (30-day token expired while the app was open) does not sign the owner out — only `useMe` does that. The PG card would show "Not authenticated" until the next `useMe` refetch. Acceptable: `useMe` runs on the same screen. Noted rather than solved.
- **Settings is becoming a stack of cards.** It already holds ACCOUNT and BACKEND; PG DETAILS makes three, and F15 wants deposits here too. If it grows further it should become a list of rows that push detail screens — not now.
- **Multiline address on Android.** `multiline` `TextInput`s ignore `numberOfLines` for height on some Android versions; set a `minHeight` in the style rather than relying on it.
- **`maxLength={2}` on the due day** stops `"100"` being typed at all, so the regex mainly catches paste and `"0"`. Keep both — the schema is what the test asserts.
- **Stale npm installs.** F0.2 and F1 both hit silently broken `node_modules`. F2 adds no dependency at all, so if Metro or Jest breaks here, suspect the install (`rm -rf node_modules && npm ci`) before the code.

## 12. Blockers and open questions

**No blockers.** F1's backend is merged with 70 passing tests: `owners`, `pgs`, the PG-at-signup transaction and
`get_current_owner` all exist. F1's checkbox is still `[~]` only because its **on-device** checklist has not been
run (it needs a fresh EAS build for `expo-secure-store`); that is a mobile-verification gap, not a code gap, and
it shares no code path with F2's work. F2 can be built while it stays open — but F1 should be ticked before F3,
so the device checklist does not quietly become per-feature debt.

| # | Question | Recommendation |
|---|---|---|
| Q1 | Should a unique index on `pgs.owner_id` enforce "one PG per owner"? | **No.** CLAUDE.md §3 wants multiple PGs supportable later without a rewrite, and the constraint would have to be dropped then. The one-PG invariant lives in `get_current_pg` (rule 3) and in the fact that only signup creates a PG. It would also mean a migration, which §5 says F2 should not need. |
| Q2 | **Decided 2026-10-21.** What should PG routes do when the owner has no PG row — 404, create one lazily, or offer the owner a "Create PG" button? | **404 `pg not found`, surfaced as a plain-language empty state — and no `POST /pg` in F2.** Auto-creating would hide a data bug, as the developer noted. A create flow was considered and deliberately dropped: the row is written in the same transaction as the owner, so its absence means a bug or a hand-deleted row, and with one owner that is a 10-second `psql` fix — not worth a new endpoint, a 409-when-one-exists rule and a second code path through the card's form. Revisit when multi-PG reaches the UI, which needs `POST /pg` anyway. |
| Q3 | **Decided 2026-10-21.** Separate "Edit PG" screen/route, or inline edit inside the Settings card? | **Inline, in `pg-details-card.tsx`.** Fewer taps for an owner in a hurry (CLAUDE.md §2), and it touches no routing — F1 showed that adding routes under `NativeTabs` is the fiddly path and forces `.expo/types/router.d.ts` to regenerate. Revisit if Settings grows past three or four cards. |
| Q4 | Should `PgRead` expose `owner_id` and `updated_at`? | **Neither.** `owner_id` is an internal FK the app never sends back, and nothing in the UI shows a "last edited" time. `OwnerRead` sets the precedent of listing only what the client needs. |
| Q5 | **Decided 2026-10-21.** `address` is `TEXT` with no limit — cap it at the API? | **Yes, 500 characters** (`Field(max_length=500)`), column unchanged. An Indian PG address fits easily; the cap just stops a pathological body being stored. It is API-layer validation, not a schema rule, so CLAUDE.md §7 does not need changing. |
| Q6 | `DEFAULT_PG_NAME` / `DEFAULT_RENT_DUE_DAY` currently live in `services/auth.py`. Move them? | **Yes, to `services/pg.py`**, with `services/auth.py` importing them. F2 creates the PG's own service module; leaving the PG's defaults in the auth module is where a second, drifting copy eventually appears. F1's `test_signup_creates_pg` is the regression net. |
| Q7 | **Decided 2026-10-21.** `PATCH /pg` with an empty body — 200 no-op or 422? | **200 no-op.** Nothing is wrong with a request that asks for no change, a 422 would make the client special-case "no fields dirty", and the response still carries the current PG. |
| Q8 | Should the card show a "Saved" confirmation after a successful PATCH? | **No** — leaving edit mode while the card shows the new values is the confirmation. A toast needs infrastructure the app does not have yet; F8's "Undo toast" is where that earns its place. |
| Q9 | *(Suggestion for later, not F2)* A PG photo/logo for reminder messages and receipts, and the owner being able to edit their own name/phone. | Out of scope — CLAUDE.md §4 rules out uploads, and owner-profile editing is not in any feature yet. Revisit in Phase 5 (F14 receipts) if the owner asks. |

## 13. Changelog

- 2026-10-21: Spec created — `GET`/`PATCH /pg`, `get_current_pg` + `CurrentPg`, `services/pg.py`, `schemas/pg.py`, `apiPatch`, a PG DETAILS card with inline editing in Settings, no schema change, and 22 acceptance criteria.
- 2026-10-21: QA pass (`qa/reports/F2-2026-10-21.md`) — no bugs; two spec corrections applied. §6 rule 6 now states that `address` is trimmed, matching §7's table and the code (SI-2). §6 rule 7, §7's error table and **AC-8** now say that a whole number sent as `"7"` or `9.0` is accepted and coerced, instead of claiming every non-integer is a 422 (SI-1); behaviour unchanged, the spec was overstating it.
- 2026-10-21: Q2, Q3, Q5 and Q7 answered by the developer. Q2 settled as a 404 shown as a "No PG set up yet." empty state with **no** `POST /pg` (auto-creation rejected, a create button considered and deferred) — added §9's 404 branch, a fourth card-test case, manual step 13 and **AC-23**, now 23 acceptance criteria. Q3 (inline edit), Q5 (500-character address cap) and Q7 (`PATCH {}` → 200 no-op) confirmed as recommended; no change to the plan.

## 14. Acceptance criteria

- **AC-1:** `GET /api/v1/pg` with a valid token returns **200** with the PG auto-created at signup: `name` `"My PG"`, `address` `null`, `default_rent_due_day` `5`. _(Source: FEATURES.md ("auto-creation on signup", "get") · Verified by: `test_get_pg_returns_signup_defaults`, `test_signup_creates_pg`, Manual step 3)_
- **AC-2:** `PATCH /api/v1/pg` with `name`, `address` and `default_rent_due_day` returns **200** with the new values, and a subsequent `GET /api/v1/pg` returns the same — the change persisted. _(Source: FEATURES.md ("update") · Verified by: `test_update_pg_all_fields`, Manual steps 5, 6, 12)_
- **AC-3:** A PATCH carrying only one field leaves the other fields exactly as they were. _(Source: Spec §6 rule 8 · Verified by: `test_update_pg_partial_leaves_other_fields`)_
- **AC-4:** `address` can be cleared — sent as `null`, `""` or whitespace it is stored and returned as `null`. _(Source: Spec §6 rule 6 · Verified by: `test_update_pg_clears_address`, Manual step 9)_
- **AC-5:** `name` is trimmed before being stored, so `"  Sri Sai PG  "` is saved and returned as `"Sri Sai PG"`. _(Source: Spec §6 rule 5 · Verified by: `test_update_pg_trims_name`, `pg-schemas.test.ts`)_
- **AC-6:** A blank, whitespace-only, explicitly `null`, or over-120-character `name` returns **422** and leaves the PG unchanged. _(Source: FEATURES.md ("validation"), Spec §6 rule 5 · Verified by: `test_update_pg_rejects_bad_name`, `pg-schemas.test.ts`, Manual step 8)_
- **AC-7:** An `address` longer than 500 characters returns **422** and leaves the PG unchanged. _(Source: Spec §6 rule 6, §12 Q5 · Verified by: `test_update_pg_rejects_long_address`, `pg-schemas.test.ts`)_
- **AC-8:** A `default_rent_due_day` outside 1–28 (`0`, `29`, `-1`, `100`), or one that is not a whole number (`"abc"`, `5.5`, `null`, `true`), returns **422** and leaves the PG unchanged. A whole number sent as a string or float in range (`"7"`, `9.0`) is accepted and stored as that integer (§6 rule 7). _(Source: **FEATURES.md** ("due day outside 1–28 rejected (422)"), CLAUDE.md §7 · Verified by: `test_update_pg_rejects_due_day_out_of_range`, `test_update_pg_rejects_non_integer_due_day`, `pg-schemas.test.ts`, Manual step 7)_
- **AC-9:** The boundary values `1` and `28` are accepted and stored. _(Source: Spec §6 rule 7 · Verified by: `test_update_pg_accepts_boundary_due_days`, `pg-schemas.test.ts`, Manual step 10)_
- **AC-10:** `PATCH /api/v1/pg` with an empty body `{}` returns **200** and changes nothing. _(Source: Spec §6 rule 8, §12 Q7 · Verified by: `test_update_pg_empty_body_is_noop`)_
- **AC-11:** `GET /api/v1/pg` and `PATCH /api/v1/pg` without a valid bearer token return **401** with `detail: "not authenticated"`, and the PATCH changes nothing. _(Source: CLAUDE.md §8, Spec §6 rule 12 · Verified by: `test_get_pg_without_token`, `test_get_pg_with_malformed_token`, `test_update_pg_without_token`)_
- **AC-12:** With two owners registered, owner A's PATCH never alters owner B's PG, and each `GET /api/v1/pg` returns only the caller's own PG. _(Source: **FEATURES.md** ("owner A cannot read or change owner B's PG"), CLAUDE.md §7 · Verified by: `test_pg_isolation_between_owners`)_
- **AC-13:** No PG response body contains `owner_id`, and a PG's `id` and `created_at` are unchanged by a PATCH. _(Source: Spec §6 rule 11, §7 · Verified by: `test_pg_response_omits_owner_id`, `test_update_pg_keeps_id_and_created_at`)_
- **AC-14:** When the authenticated owner has no PG row, both PG routes return **404** with `detail: "pg not found"`. _(Source: Spec §6 rule 4, §12 Q2 · Verified by: `test_pg_routes_404_when_owner_has_no_pg`)_
- **AC-15:** A successful PATCH advances the PG row's `updated_at` past its `created_at`. _(Source: Spec §6 rule 10 · Verified by: `test_update_pg_bumps_updated_at`)_
- **AC-16:** Settings shows a PG DETAILS section with the PG's name, address (or an explicit "no address yet") and rent due day, and an Edit mode whose fields are prefilled from the current values. _(Source: **FEATURES.md** ("PG details section in Settings, editable") · Verified by: `pg-details-card.test.tsx`, Manual steps 3, 4, 5)_
- **AC-17:** After a successful save the card shows the new values without a manual refresh, because the `['pg']` query cache is updated from the PATCH response. _(Source: Spec §9 · Verified by: `use-update-pg.test.tsx`, Manual step 5)_
- **AC-18:** `apiPatch` sends `method: "PATCH"` with `Content-Type: application/json`, the JSON body and the bearer header, and rejects with an `ApiError` carrying the HTTP status and the server's `detail` on a non-2xx response. _(Source: Spec §9, CLAUDE.md §8 · Verified by: `client-patch.test.ts`)_
- **AC-19:** `uv run pytest`, `uv run ruff check .`, `npx tsc --noEmit` (strict) and `npm test` all pass. _(Source: CLAUDE.md §9, §10 · Verified by: Manual steps 1, 2)_
- **AC-20:** A PG request that fails — server unreachable or a 422 — shows a readable message in Settings, keeps the typed values in the form, and does not crash the screen. _(Source: Spec §9, §11 · Verified by: `pg-details-card.test.tsx`, Manual step 11)_
- **AC-21:** `uv run alembic check` reports no model/migration drift — F2 adds no migration. _(Source: Spec §5, CLAUDE.md §5 · Verified by: Manual step 1)_
- **AC-22:** A PG row with `default_rent_due_day` outside 1–28 still cannot be stored in the database, independently of the API validation. _(Source: CLAUDE.md §7, Spec §6 rule 13 · Verified by: `test_pgs_due_day_check_constraint` (existing, F1))_
- **AC-23:** When the PG request returns 404, Settings shows "No PG set up yet." with a line telling the owner to contact support, offers no Edit button, and never shows the raw `pg not found` text. _(Source: Spec §6 rule 4, §12 Q2 · Verified by: `pg-details-card.test.tsx`, Manual step 13)_
