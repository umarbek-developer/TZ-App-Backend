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

## 5. Authorization

- [ ] **Z1** — Request with **no/invalid/expired/revoked token → 401**.
- [ ] **Z2** — Request **authenticated but lacking the permission → 403**. The 401-vs-403 split must
      be exact; this is the single most-tested behaviour in the assignment.
- [ ] **Z3** — Permission resolution: `User → UserRole → Role → RolePermission → Permission.code`.
      A user's effective permission set is the **union** across all their roles.
- [ ] **Z4** — Permission classes are custom subclasses of DRF `BasePermission` (explicitly allowed).
      No `IsAuthenticated`, `IsAdminUser`, or `DjangoModelPermissions` (C9).
- [ ] **Z5** — A reusable permission check keyed by code string (the assignment's "Permission
      Decorator"), so a view declares e.g. `mock.view` once.
- [ ] **Z6** — Guest (no permissions) gets 403 on every permission-gated endpoint but still passes
      the authenticated-only endpoints (logout, profile).

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

- [ ] **E7** — `GET /roles` ✅ `role.view`
- [ ] **E8** — `POST /roles` ✅ `role.update`
- [ ] **E9** — `PATCH /roles/{id}` ✅ `role.update`
- [ ] **E10** — `DELETE /roles/{id}` ✅ `role.update`
- [ ] **E11** — `GET /permissions` ✅ `permission.view`
- [ ] **E12** — `POST /permissions` ✅ `permission.update`
- [ ] **E13** — `PATCH /permissions/{id}` ✅ `permission.update`
- [ ] **E14** — `DELETE /permissions/{id}` ✅ `permission.update`
- [ ] **E15** — `POST /assign-role` ✅ `role.update` — body `{"user":1,"roles":[2,3]}`
- [ ] **E16** — `POST /assign-permission` ✅ `permission.update` — body
      `{"role":2,"permissions":[5,6,7]}`

### Mock (no database — static JSON)

- [ ] **E17** — `GET /mock/projects` ✅ `mock.view` → `[{"id":1,"name":"CRM"},{"id":2,"name":"ERP"}]`
- [ ] **E18** — `GET /mock/orders` ✅ `mock.view` → `[{"id":100,"price":500}]`

---

## 7. Seed data

- [ ] **S1** — A management command creates the seed set (template slot:
      `src/apps/utils/management/commands/`).
- [ ] **S2** — Administrator: `admin@mail.com` / `password123`.
- [ ] **S3** — Roles: `Admin`, `Manager`, `Employee`, `Guest`.
- [ ] **S4** — Permissions (the Seed Data list — 8 codes): `user.view`, `user.update`, `user.delete`,
      `mock.view`, `role.view`, `role.update`, `permission.view`, `permission.update`.
      ⚠️ The Database-Design examples also list `user.create` (9 codes) — see §9 Q6.
- [ ] **S5** — Admin → all permissions.
- [ ] **S6** — Manager → `mock.view`, `user.view`.
- [ ] **S7** — Employee → `mock.view`.
- [ ] **S8** — Guest → none.
- [ ] **S9** — The command is idempotent (re-running does not duplicate or crash).

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
- **Q6** — `user.create`: in the Database-Design permission examples, absent from Seed Data. Seed 8
  codes or 9?
- **Q7** — There are **no `/users` endpoints** in the API Summary, yet `user.view`/`user.update`/
  `user.delete` are seeded. Are user-management endpoints expected, or are these placeholders? As
  written they are unreachable.
- **Q8** — Does registration auto-assign a default role (e.g. `Guest`)? Currently it assigns none.
- **Q9** — Does `is_superuser = True` bypass permission checks, or must Admin's power come only from
  seeded role→permission rows?
- **Q10** — Seed admin password `password123` fails the `AUTH_PASSWORD_VALIDATORS` now enforced at
  registration (too common / no symbol). The seed command bypasses the serializer so it will work,
  but the two are inconsistent — intended?
- **Q11** — Are `Role.name` and `Permission.code` unique? Implied but never stated; affects the
  idempotent seed (S9).

---

## 10. Process gate (per HARD CONSTRAINTS)

Every step ends with **all four**, in order:

- [ ] tests written
- [ ] `pytest` green
- [ ] `ruff` clean
- [ ] `git commit`

Postgres only — no sqlite, including in tests.
