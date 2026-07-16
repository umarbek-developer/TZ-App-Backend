# SPEC — RBAC Backend

Derived from [docs/assignment.md](docs/assignment.md) (source of record) and the HARD CONSTRAINTS in
[CLAUDE.md](CLAUDE.md). Where the two disagree, the conflict is listed in §1 and **not** silently
resolved; every affected requirement below is tagged with its conflict ID.

Status key: `[ ]` not started · `[x]` done · `[?]` blocked on a decision in §1 or §9.

---

## 1. Conflict register — RESOLVED 2026-07-16

The assignment mandated the exact stack the HARD CONSTRAINTS forbade. The project owner resolved it
**in favour of the assignment**: *"Implement complete authentication using Django REST Framework and
SimpleJWT"*, *"blacklist refresh token"*, *"The Custom User model is already implemented. DO NOT
recreate models."*

| ID | Assignment says | HARD CONSTRAINT said | **Resolution** |
| --- | --- | --- | --- |
| **C1** | "Use `djangorestframework-simplejwt`" | From scratch; PyJWT HS256 | ✅ **Assignment wins.** SimpleJWT (PyJWT HS256 underneath) |
| **C2** | Logout = "Blacklist Refresh Token" | Own `revoked_tokens` table | ✅ **Assignment wins.** SimpleJWT `token_blacklist` |
| **C3** | Login returns `{refresh, access}` | Single token `{user_id, jti, iat, exp}` | ✅ **Assignment wins.** Pair returned. The access token payload happens to be exactly `{user_id, jti, iat, exp}` + `token_type` |
| **C4** | Hashing unspecified | bcrypt, never Django hashers | ✅ **Assignment wins.** Django pbkdf2 — the existing `User.check_hash_password()` hard-codes `pbkdf2_sha256` |
| **C5** | `python-decouple` | — | ✅ **Template wins.** `django-environ` kept |
| **C6** | Single `config/settings.py` | — | ✅ **Template wins.** Split kept |
| **C7** | `requirements.txt` at root | — | ✅ **Template wins.** `src/requirements/` chain kept |
| **C8** | `apps/{accounts,rbac,mock}/` self-contained | — | ✅ **Template + directive win.** See §2 |
| **C9** | "Authenticated" column | `IsAuthenticated` forbidden | ✅ **Assignment wins.** DRF `IsAuthenticated` |
| **C10** | `is_staff`, `is_superuser` | `AbstractUser` forbidden | ✅ **Assignment wins.** `AbstractUser` kept |
| **C11** | `Pillow` in packages | — | Kept installed (template dep); unused by this API |
| **C12** | Prefix `/api/` | — | ✅ **Template wins.** `/api/v1/` (owner confirmed) |

**Surviving constraints:** 401 vs 403 semantics; PostgreSQL only; every step ends with tests written,
pytest green, ruff clean, git commit.

---

## 2. Placement (per your directives + template conventions)

- [ ] **P1** — Models live in `src/apps/`. New Django apps: `apps.accounts` (User, RevokedToken) and
      `apps.rbac` (Role, Permission, RolePermission, UserRole). Registered in `INSTALLED_APPS` as
      `'apps.accounts'` / `'apps.rbac'`.
- [ ] **P2** — The backend (HTTP layer) lives inside `src/api/`. Per directive: serializers in
      `src/api/user/serializers/`, views in `src/api/user/views/`, backend URLs in
      `src/api/user/urls.py`.
- [ ] **P3** — `src/api/urls.py` is the main API urlconf that aggregates the rest. *(Reading of
      "amin urls" as "main urls" — see §9 Q1.)*
- [ ] **P4** — `mock` needs no models (assignment: "No database needed"), so it is HTTP-only: views
      under `src/api/user/views/`, no app under `src/apps/`.
- [ ] **P5** — Custom auth middleware + JWT + bcrypt helpers live in `apps/accounts/`
      (`middleware.py`, `tokens.py`, `passwords.py`) since they are imported by settings, not by a
      view.
- [ ] **P6** — Permission-checking classes live in `apps/rbac/permissions.py`, consumed by
      `src/api/user/views/`.

---

## 3. Data model

- [ ] **D1** — `User`: `id`, `first_name`, `last_name`, `middle_name`, `email` (unique), `password`,
      `is_active`, `is_staff`, `is_superuser`, `created_at`, `updated_at`.
- [ ] **D2** — `User` must **not** inherit `AbstractUser`/`AbstractBaseUser`/`PermissionsMixin`
      (C10). Plain `models.Model`.
- [ ] **D3** — `User.id` is an **integer** PK — the assign-role payload (`"user":1`) and
      assign-permission payload (`"permissions":[5,6,7]`) are integers. *(The old template `User`
      used a UUID PK; that app is being replaced — see §8.)*
- [ ] **D4** — `User.password` stores a **bcrypt** hash (C4).
- [ ] **D5** — `Role`: `id`, `name`, `description`.
- [ ] **D6** — `Permission`: `id`, `code`, `name`, `description`.
- [ ] **D7** — `RolePermission`: M2M `role` ↔ `permission`.
- [ ] **D8** — `UserRole`: M2M `user` ↔ `role`. A user may hold several roles.
- [ ] **D9** — `RevokedToken`: stores `jti` (unique, indexed) + revocation timestamp. Required by
      the constraints; has no counterpart in the assignment (C2).

---

## 4. Authentication — DONE (commit: auth step)

- [x] **A1** — Tokens issued by SimpleJWT (HS256 via PyJWT). Verified access payload:
      `{token_type, exp, iat, jti, user_id}`.
- [x] **A2** — Passwords hashed via `set_password()` → `pbkdf2_sha256` (C4). Test:
      `test_register_hashes_the_password`.
- [x] **A3** — `JWTAuthentication` is the sole `DEFAULT_AUTHENTICATION_CLASSES` entry; Session and
      Basic removed.
- [x] **A4** — `request.user` is set by SimpleJWT; inactive users are rejected via
      `CHECK_USER_IS_ACTIVE` (default `True`).
- [x] **A5** — Logout blacklists the refresh token (C2). Test: `test_logout_blacklists_the_refresh_token`.
- [x] **A6** — Login rejects `is_active = False`. Test: `test_login_rejects_inactive_user`.
- [x] **A7** — Registration validates `password == confirm_password`.
- [x] **A8** — Registration rejects duplicate email, **case-insensitively**.
- [x] **A9** — No `login()`/`logout()`/`authenticate()`/`@login_required`; no Session/Basic auth.
- [x] **A10** — Registration forces `is_active=True` (the model defaults it to `False`, a leftover of
      the template's OTP flow, which would otherwise make every new account unable to log in).

---

## 5. Authorization — DONE (commit: rbac permission layer)

Helpers in `src/apps/rbac/services.py`; permission classes in `src/apps/rbac/permissions.py`.

- [x] **Z1** — No/invalid token → **401**. `test_anonymous_gets_401`.
- [x] **Z2** — Authenticated but lacking the code → **403**.
      `test_authenticated_without_permission_gets_403`. The split is DRF's own: returning `False`
      raises `NotAuthenticated` (401) when no authenticator succeeded, `PermissionDenied` (403) when
      one did. ⚠️ Only holds while the view keeps an authenticator that emits a
      `WWW-Authenticate` header — `authentication_classes = []` collapses both to 403.
- [x] **Z3** — `User → UserRole → Role → RolePermission → Permission.code`, unioned across roles.
      `test_permissions_union_across_multiple_roles`, `test_overlapping_roles_do_not_duplicate_codes`.
- [x] **Z4** — `HasPermission` subclasses DRF `BasePermission` with fully custom logic.
- [x] **Z5** — Reusable two ways: `permission_classes = [require_permissions('mock.view')]` (factory)
      or `permission_classes = [HasPermission]` + `required_permissions = 'role.view'` on the view.
      `require_all=False` gives any-of semantics.
- [x] **Z6** — Guest (no permissions) → 403 on gated endpoints. `test_role_without_the_code_gets_403`.
- [x] **Z7** — **Fails closed.** `HasPermission` with no declared code raises `ImproperlyConfigured`
      rather than allowing every authenticated user.
- [x] **Z8** — **Query cost:** one query per request regardless of role count, memoised on the user
      instance for the request's lifetime; zero queries for anonymous.
      `test_resolution_is_a_single_query_regardless_of_role_count`, `test_repeat_lookups_hit_the_cache`.
- [x] **Z9** — Inactive users hold nothing even if their roles grant codes
      (`test_inactive_user_is_denied_even_holding_the_code`).
- [x] **Z10** — ✅ **Answers Q9.** `is_superuser` does **not** bypass permission checks; authorization
      is purely database-driven. Owner's decision: the admin's power comes from the seeded Admin role
      instead (S2), keeping `User → Roles → Permissions` the only authorization path. A superuser
      holding no roles is denied every gated endpoint — by design.

---

## 6. Endpoints

Prefix pending §9 Q3. Auth column: ❌ = public, ✅ = valid Bearer token required.

### Account (authenticated-only, no permission code) — DONE

All at `/api/v1/…`, implemented in `src/api/auth/`.

- [x] **E1** — `POST /auth/register/` ❌ → **201**. Body `{first_name, last_name, middle_name, email,
      password, confirm_password}`.
- [x] **E2** — `POST /auth/login/` ❌ → **200** `{refresh, access}`. Bad creds / inactive → **401**.
- [x] **E3** — `POST /auth/logout/` ✅ → **205**. Body `{refresh}`. Reuse → **400**.
- [x] **E4** — `GET /auth/profile/` ✅ → **200**.
- [x] **E5** — `PATCH /auth/profile/` ✅ → **200**.
- [x] **E6** — `DELETE /auth/profile/` ✅ → **204**. Soft delete; every outstanding refresh token is
      blacklisted; the access token dies at once; login is refused thereafter.

### RBAC admin

Role CRUD **DONE** — `ModelViewSet` at `src/api/user/views/role_views.py`, routed at
`/api/v1/roles/` (owner's choice; `api.user.urls` is now mounted at the root).
⚠️ Gated on the **seeded** `role.view`/`role.manage` codes, not the assignment's `role.update`
(Q13) — `role.update` does not exist in the database, so gating on it would deny everyone.
"Administrator only" is an emergent property: only the Admin role holds these codes.

- [x] **E7** — `GET /roles/` ✅ `role.view` — paginated, searchable, orderable.
- [x] **E7b** — `GET /roles/{id}/` ✅ `role.view`.
- [x] **E8** — `POST /roles/` ✅ `role.manage` → 201.
- [x] **E9** — `PATCH /roles/{id}/` ✅ `role.manage` → 200.
- [x] **E9b** — `PUT /roles/{id}/` ✅ `role.manage` → 200.
- [x] **E10** — `DELETE /roles/{id}/` ✅ `role.manage` → 204.
- [x] **E10b** — Pagination (`?page`, `?page_size`), search over name+description (`?search`),
      ordering (`?ordering=name|created_at|updated_at`, `-` to reverse).
- [x] **E10c** — Validation: name required, non-blank, ≤100 chars, trimmed, unique
      **case-insensitively**. `id`/`permissions`/`created_at`/`updated_at` are read-only.
- [x] **E10d** — Documented in Swagger per action, including the 401/403 responses.
Permission CRUD **DONE** — `ModelViewSet` at `src/api/user/views/permission_views.py`, routed at
`/api/v1/permissions/`. Gated on the seeded `permission.view`/`permission.manage` (Q13, as with
roles).

- [x] **E11** — `GET /permissions/` ✅ `permission.view` — paginated, filterable, searchable,
      orderable.
- [x] **E11b** — `GET /permissions/{id}/` ✅ `permission.view`.
- [x] **E12** — `POST /permissions/` ✅ `permission.manage` → 201.
- [x] **E13** — `PATCH /permissions/{id}/` ✅ `permission.manage` → 200.
- [x] **E13b** — `PUT /permissions/{id}/` ✅ `permission.manage` → 200.
- [x] **E14** — `DELETE /permissions/{id}/` ✅ `permission.manage` → 204.
- [x] **E14b** — **Filtering** (`PermissionFilter` in `src/api/user/filters.py`): `?code=` (exact,
      case-insensitive), `?code_contains=`, `?namespace=user` (everything under `user.*`), `?name=`,
      `?role=<uuid>`, `?role_name=`, `?unassigned=`, `?created_after=`/`?created_before=`.
      Distinct from `?search=`, which loosely matches code+name+description.
- [x] **E14c** — Ordering: `?ordering=code|name|created_at|updated_at`.
- [x] **E14d** — Validation: `code` required, ≤100 chars, **lowercased on write**, must match
      `^[a-z0-9]+(?:[._-][a-z0-9]+)*$`, unique case-insensitively. Rationale: permission checks
      compare codes by exact string, so a stored `Mock.View` could never match anything the API asks
      for. `id`/`roles`/`created_at`/`updated_at` are read-only.
- [x] **E14e** — Documented in Swagger per action, including 401/403.
Assign-role **DONE** — `APIView` at `src/api/user/views/assign_role_views.py`, routed at
`/api/v1/assign-role/`. All three operations ride one endpoint, split by verb. Gated on
`role.manage`.

- [x] **E15** — `POST /api/v1/assign-role/` ✅ `role.manage` → 200. **Adds** roles, keeping existing
      ones. Body `{"user": "<uuid>", "roles": ["<uuid>", ...]}`.
      ⚠️ The assignment's example body is `{"user":1,"roles":[2,3]}` — **integers**. UUIDs are used
      because the owner specified UUID pks for both `User` and `Role` (SPEC D3 / rbac step).
- [x] **E15b** — `PUT /api/v1/assign-role/` ✅ `role.manage` → 200. **Replaces** the user's roles
      with exactly the given list. An empty list strips every role (POST/DELETE reject empty).
- [x] **E15c** — `DELETE /api/v1/assign-role/` ✅ `role.manage` → 200 with a body (not 204, since the
      spec asks for clean JSON responses). **Removes** the given roles, leaving the rest.
- [x] **E15d** — Validation: user must exist, every role must exist, no duplicate ids in the payload,
      role list non-empty (except on PUT). One unknown id rejects the whole request — the writes are
      wrapped in `transaction.atomic`, so a partially-valid payload lands nothing.
- [x] **E15e** — Duplicates prevented two ways: an already-held role is a **no-op** reported under
      `already_assigned` rather than an error, and `bulk_create(ignore_conflicts=True)` keeps a
      concurrent identical request from turning the unique constraint into a 500.
- [x] **E15f** — Responses report the resulting state plus what changed:
      `{user: {...}, roles: [...], added: [...], already_assigned: [...]}` (POST),
      `+ removed/unchanged` (PUT), `{removed, not_assigned}` (DELETE).
- [x] **E15g** — `clear_permission_cache()` is called after every mutation.
- [x] **E15h** — Documented in Swagger per verb, including 400/401/403.
- [ ] **E16** — `POST /assign-permission` ✅ `permission.update` — body
      `{"role":2,"permissions":[5,6,7]}`

### Mock (no database — static JSON)

- [ ] **E17** — `GET /mock/projects` ✅ `mock.view` → `[{"id":1,"name":"CRM"},{"id":2,"name":"ERP"}]`
- [ ] **E18** — `GET /mock/orders` ✅ `mock.view` → `[{"id":100,"price":500}]`

---

## 7. Seed data — DONE (commit: seed step)

- [x] **S1** — `python manage.py seed_data`, at
      `src/apps/rbac/management/commands/seed_data.py` (placed with the models it seeds rather than
      in the generic `apps/utils/` slot).
- [x] **S2** — Administrator seeded as **`admin@gmail.com` / `admin123`** (owner's choice, per the
      README — deliberately *not* the assignment's `admin@mail.com` / `password123`). Created as a
      superuser **and granted the Admin role**, which is what actually confers its permissions.
      Idempotent: an existing account keeps its password and only has its flags/role ensured.
- [x] **S3** — Roles: `Admin`, `Manager`, `Employee`, `Guest`.
- [x] **S4** — Permissions, **8 codes as re-specified by the owner**: `user.view`, `user.update`,
      `user.delete`, `role.view`, `role.manage`, `permission.view`, `permission.manage`, `mock.view`.
      ⚠️ This **changes two codes** vs the assignment: `role.update` → `role.manage` and
      `permission.update` → `permission.manage`. The assignment's API Summary still names the old
      codes — see §9 Q13. Resolves Q6: `user.create` is **not** seeded.
- [x] **S5** — Admin → all 8.
- [x] **S6** — Manager → `mock.view`, `user.view`.
- [x] **S7** — Employee → `mock.view`.
- [x] **S8** — Guest → none.
- [x] **S9** — Idempotent. Verified by re-running against the real database (0 rows created on the
      second pass) and by `test_running_three_times_is_stable`. `--prune` additionally reconciles
      away undeclared grants; the default is additive so hand-made grants survive.

---

## 8. Template cleanup this spec implies

- [x] **T1** — ~~Delete `apps/users/`~~ **Cancelled.** Owner: *"DO NOT recreate models."* `User` is
      kept as-is; only an additive `middle_name` field was added (migration `0016`), because the
      assignment's register payload requires it and the model had no such field.
- [x] **T2** — `api/auth/` cut from 11 OTP/change-email/forget-password routes to the 4 URL patterns
      (6 operations) the assignment specifies. 9 template files deleted.
- [x] **T3** — ~~Remove `contrib.auth`~~ **Cancelled** (C10). `AUTH_PASSWORD_VALIDATORS` is now
      actively used by registration.
- [x] **T4** — ~~Remove simplejwt~~ **Cancelled** (C1). Added `token_blacklist` to `INSTALLED_APPS`.
- [ ] **T5** — Remove celery + redis (`config/celery.py`, `CELERY_*` settings, both packages).
      `api/auth/tasks.py` is already deleted. Verified inert — nothing imports them.
- [x] **T6** — `send_mail_sms.py` + `tasks.py` deleted. ⚠️ `templates/verify_email*.html` and the
      `EMAIL_*` settings are now orphaned but harmless — left for the cleanup step.
- [ ] **T7** — Drop the `TemplateView` index route + `templates/` + `static/` wiring, together.
- [x] **T8** — Postgres forced: `base.py` raises `ImproperlyConfigured` unless `DB_TYPE == "psql"`;
      `.env`/`.env.example` updated; sqlite fallback gone.
- [x] **T9** — `common.txt` normalized UTF-16LE → UTF-8. `pytest`, `pytest-django`, `ruff` added to
      `dev.txt`. (`bcrypt`/`PyJWT` not needed: superseded by C1/C4; PyJWT arrives via SimpleJWT.)
- [x] **T10** — pytest + ruff configured in repo-root `pyproject.toml`.
- [ ] **T11** — Decide the fate of `django.contrib.admin` + jazzmin (§9 Q4). Lower-stakes now.
- [x] **T12** — `cp .env.example .env` documented in `CLAUDE.md`, with the SECRET_KEY + createdb steps.
- [x] **T13** — `drf-spectacular` wired: `/api/v1/schema/`, `/api/v1/docs/`, `/api/v1/redoc/`.
      Schema generates with 0 errors / 0 warnings.
- [x] **T14** — **Security:** `SECRET_KEY` was the 4-character literal `test`, signing every JWT with
      a 4-byte HMAC key (PyJWT emitted `InsecureKeyLengthWarning`). Replaced with a generated 50-char
      key; `.env.example` now documents how to generate one.
- [x] **T15** — **Latent bug fixed:** `apps/utils/BaseModel.deleted_by` reused `updated_by`'s
      `related_name`. Dormant only because nothing inherits `BaseModel`; the first concrete subclass
      (i.e. the RBAC models) would have failed `fields.E304/E305` at startup.

---

## 9. Open questions

### Answered

- **Q1** — ✅ `src/api/urls.py` = **main** urls (aggregator). It also now mounts the API docs.
- **Q2** — ✅ **(C3)** Access + refresh pair, per the assignment.
- **Q3** — ✅ **(C12)** `/api/v1/` prefix.
- **Q5** — ⚠️ **Decided by implementation, confirm if wrong.** `PATCH /auth/profile/` accepts
  `first_name`, `last_name`, `middle_name`, `email` (uniqueness-checked). `id`, `is_active` and
  `date_joined` are read-only — a writable `is_active` would let a soft-deleted user reactivate
  themselves. Password change is **not** exposed; no endpoint for it exists in the assignment.

### Still open — needed for the RBAC step

- **Q4** — Keep `django.contrib.admin` + jazzmin, or drop them? Now lower-stakes: `AbstractUser` is
  staying, so `UserAdmin` still works. Default is to keep.
- **Q6** — ✅ **Answered.** 8 codes; `user.create` is not seeded.
- **Q7** — There are **no `/users` endpoints** in the API Summary, yet `user.view`/`user.update`/
  `user.delete` are seeded. Are user-management endpoints expected, or are these placeholders? As
  written they are unreachable.
- **Q8** — Does registration auto-assign a default role (e.g. `Guest`)? Currently it assigns none, so
  **every registered user is denied every permission-gated endpoint** until given a role by hand.
- **Q9** — ✅ **Answered.** No superuser bypass; see Z10.
- **Q10** — ⚠️ The seeded admin password `admin123` fails the `AUTH_PASSWORD_VALIDATORS` enforced at
  registration (too short / too common / no symbol). The seed bypasses the serializer so it works,
  but the same password could not be used to register. Accepted for now.
- **Q12** — ✅ **Answered.** Seed creates `admin@gmail.com` / `admin123` (S2).
- **Q11** — ✅ **Answered by implementation.** `Role.name` and `Permission.code` are unique, and both
  join tables carry `UniqueConstraint`s.
- **Q12** — **The seed does not create the `admin@mail.com` / `password123` administrator.** The
  owner's instruction listed only roles/permissions/grants; the assignment asks for the account.
  Should `seed_data` create it (and if so, superuser or Admin-role-holder)?
- **Q13** — **Permission codes diverge from the assignment.** The seed now uses `role.manage` and
  `permission.manage`, but the assignment's API Summary gates `POST/PATCH/DELETE /roles` on
  `role.update` and `POST/PATCH/DELETE /permissions` on `permission.update`. The API step needs to
  know which naming wins. Assumption: the newer `*.manage` codes.

---

## 10. Process gate (per HARD CONSTRAINTS)

Every step ends with **all four**, in order:

- [ ] tests written
- [ ] `pytest` green
- [ ] `ruff` clean
- [ ] `git commit`

Postgres only — no sqlite, including in tests.
