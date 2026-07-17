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

## 2. Placement — DONE

- [x] **P1** — Models live in `src/apps/`: `apps.users` (the existing `User`, kept per the owner's
      "DO NOT recreate models") and `apps.rbac` (Role, Permission, UserRole, RolePermission).
      ⚠️ `apps.accounts` from the original plan was **never created** — C1/C10 made it moot.
- [x] **P2** — The backend lives inside `src/api/`: serializers in `src/api/user/serializers/`,
      views in `src/api/user/views/`, URLs in `src/api/user/urls.py`, per directive.
- [x] **P3** — `src/api/urls.py` is the main API urlconf and mounts the docs.
- [x] **P4** — `mock` has no models: views only, in `src/api/user/views/mock_views.py`.
- [x] **P5** — ~~Custom middleware/JWT/bcrypt in `apps/accounts/`~~ **Cancelled** (C1/C4). SimpleJWT
      provides authentication; no custom middleware exists.
- [x] **P6** — Permission classes in `apps/rbac/permissions.py`, consumed by `src/api/user/views/`.

---

## 3. Data model — DONE

- [x] **D1** — `User`: `id`, `first_name`, `last_name`, `middle_name`, `email` (unique), `password`,
      `is_active`, `is_staff`, `is_superuser`. ⚠️ `created_at`/`updated_at` do not exist; the
      inherited `date_joined` serves instead. `middle_name` was added (migration `0016`) — the
      assignment's register payload needs it and the model had no such field.
- [x] **D2** — ~~`User` must not inherit `AbstractUser`~~ **Cancelled** (C10). It does, per the
      owner's "DO NOT recreate models".
- [x] **D3** — ⚠️ `User.id` is a **UUID**, not the integer the assignment's `{"user":1}` implies.
      Owner's instruction ("UUID id") supersedes; `Role`/`Permission` match.
- [x] **D4** — ~~bcrypt~~ **Cancelled** (C4). Django `pbkdf2_sha256` via `set_password()`.
- [x] **D5** — `Role`: `id` (UUID), `name` (unique), `description`, `created_at`, `updated_at`.
- [x] **D6** — `Permission`: `id` (UUID), `code` (unique), `name`, `description`, timestamps.
- [x] **D7** — `RolePermission`: role ↔ permission, unique together.
- [x] **D8** — `UserRole`: user ↔ role, unique together. A user may hold several roles.
- [x] **D9** — ~~`RevokedToken`~~ **Cancelled** (C2). SimpleJWT's `token_blacklist` app instead.

⚠️ **Still present, dead:** `apps/users` also carries four unused template models —
`UserOTPVerifications`, `UserOTPIDVerifications`, `ChangePasswordLogs`, `ChangeEmailLogs` (migrations
`0002`–`0015`). Nothing references them; their methods have zero call sites. **Not removed:** they own
real tables, so dropping them is a destructive migration, and the owner's "DO NOT recreate models"
covers this app. See §9 Q16.

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
Assign-permission **DONE** — `APIView` at `src/api/user/views/assign_permission_views.py`, routed at
`/api/v1/assign-permission/`. Same one-endpoint/three-verbs shape as assign-role. Gated on
`permission.manage`.

- [x] **E16** — `POST /api/v1/assign-permission/` ✅ `permission.manage` → 200. **Adds** permissions,
      keeping existing ones. Body `{"role": "<uuid>", "permissions": ["<uuid>", ...]}` (UUIDs, not
      the assignment example's integers — see E15).
- [x] **E16b** — `PUT /api/v1/assign-permission/` ✅ → 200. **Replaces**; empty list strips all.
- [x] **E16c** — `DELETE /api/v1/assign-permission/` ✅ → 200 with a body. **Removes** the given
      permissions.
- [x] **E16d** — Validation: role and every permission must exist; no duplicate ids in the payload;
      list non-empty except on PUT. One unknown id rejects the whole request (`transaction.atomic`).
- [x] **E16e** — Duplicates: an already-carried permission is a no-op reported under
      `already_assigned`; `bulk_create(ignore_conflicts=True)` covers the concurrent-request race.
- [x] **E16f** — **Changes take effect immediately.** Every holder of the role sees the new
      permissions on their very next request — no re-login, no token refresh. This falls out of the
      design: codes are resolved from the database per request and memoised only for that request's
      lifetime. The caller's own cache is dropped explicitly (`clear_permission_cache(request.user)`)
      because they are the one live user object in the process and may have just edited their own
      role. Verified over HTTP with a token issued *before* the grant: 403 → grant → 200 → revoke →
      403. Test coverage uses real JWTs, not `force_authenticate`, since the latter pins one user
      instance and would mask exactly this.
- [x] **E16g** — Documented in Swagger per verb, including the immediacy note and 400/401/403.

### Mock (no database — static JSON) — DONE

`APIView`s at `src/api/user/views/mock_views.py`. No models, no tables, no migrations — the payloads
are module constants. All four gated on `mock.view`, held by Admin, Manager and Employee.

- [x] **E17** — `GET /api/v1/mock/projects/` ✅ `mock.view` →
      `[{"id":1,"name":"CRM"},{"id":2,"name":"ERP"}]` (verbatim from the assignment).
- [x] **E18** — `GET /api/v1/mock/orders/` ✅ `mock.view` → `[{"id":100,"price":500}]` (verbatim).
- [x] **E18b** — `GET /api/v1/mock/employees/` ✅ `mock.view` → 3 items
      `{id, first_name, last_name, position}`. Not in the assignment; shape invented to match.
- [x] **E18c** — `GET /api/v1/mock/documents/` ✅ `mock.view` → 3 items `{id, title, type}`. Not in
      the assignment; shape invented to match.
- [x] **E18d** — Anonymous → 401, authenticated without `mock.view` → 403, with it → 200. Verified
      over HTTP across every seeded role: Admin/Manager/Employee 200, Guest 403, anonymous 401.
- [x] **E18e** — Responses are **bare JSON arrays**, not the project's paginated envelope — the
      assignment specifies the array shape, and an `APIView` does not apply
      `DEFAULT_PAGINATION_CLASS`.
- [x] **E18f** — Only GET is offered; POST → 405.
- [x] **E18g** — Documented in Swagger with a response serializer per resource (documentation only —
      the views return the constants). A test asserts each payload's keys match its serializer, so
      the two cannot drift.
- [x] **E18h** — Each request costs exactly **one** query (resolving the caller's permissions) and
      **zero** data queries — asserted, which is what "no database tables" means in practice.
- [x] **E18i** — Payloads are `deepcopy`-ed per response. The views hand out module-level constants
      that live for the life of the process; anything mutating `response.data` would otherwise
      corrupt them for every later request. A test caught this.

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
- [x] **T5** — **Done (audit).** Removed `config/celery.py`, all `CELERY_*` settings, and `celery` +
      `redis` from `common.txt`. Verified inert first: the app import in `config/__init__.py` was
      100% commented out, so `autodiscover_tasks()` never ran.
- [x] **T6** — **Done (audit).** `send_mail_sms.py`/`tasks.py` deleted earlier; the audit removed the
      orphaned `templates/verify_email*.html` and every `EMAIL_*` setting. Nothing in the codebase
      sends mail (`grep` for `send_mail|EmailMessage|get_connection` → zero hits).
- [x] **T7** — **Done (audit).** Dropped the `TemplateView` index route, `templates/`, `static/` and
      `images/`. ⚠️ Worth knowing why: the scaffold's `index.html` served at `/` carried the template
      author's own name and LinkedIn/GitHub links — shipping in this deliverable. `static/css` and
      `static/js` were 0 bytes; `images/default.webp` was referenced nowhere.
- [x] **T8** — Postgres forced: `base.py` raises `ImproperlyConfigured` unless `DB_TYPE == "psql"`;
      `.env`/`.env.example` updated; sqlite fallback gone.
- [x] **T9** — `common.txt` normalized UTF-16LE → UTF-8. `pytest`, `pytest-django`, `ruff` added to
      `dev.txt`. (`bcrypt`/`PyJWT` not needed: superseded by C1/C4; PyJWT arrives via SimpleJWT.)
- [x] **T10** — pytest + ruff configured in repo-root `pyproject.toml`.
- [x] **T11** — **Resolved (audit): keep.** Not dead — `django.contrib.admin` hosts the RBAC model
      admin (Role/Permission/UserRole/RolePermission, verified rendering), and jazzmin skins it.
      `AbstractUser` stays, so `UserAdmin` still works. Closes Q4.
- [x] **T12** — `cp .env.example .env` documented in `CLAUDE.md`, with the SECRET_KEY + createdb steps.
- [x] **T13** — `drf-spectacular` wired: `/api/v1/schema/`, `/api/v1/docs/`, `/api/v1/redoc/`.
      Schema generates with 0 errors / 0 warnings.
- [x] **T14** — **Security:** `SECRET_KEY` was the 4-character literal `test`, signing every JWT with
      a 4-byte HMAC key (PyJWT emitted `InsecureKeyLengthWarning`). Replaced with a generated 50-char
      key; `.env.example` now documents how to generate one.
- [x] **T16** — **Audit removals** (all proven unused by grep before deletion): `apps/utils/` (one
      abstract `BaseModel` nothing inherited — no tables, so no migration needed); `api/admin/`
      (whose only route was a scaffold health-check absent from the assignment, and whose
      `DefaultRouter` had zero registrations); the empty stubs `api/serializers.py`, `api/views.py`,
      `api/{auth,user}/helpers.py`; the triplicated-but-unused `ReadOnly` permission and
      `UserDeactivated` exception; `api/auth/filters.py` (a commented-out filter for a `Product`
      model that never existed); `User.token()`; and the duplicate `ObjectPaginationClass` /
      `ItemPagination`.
- [x] **T17** — **Dead settings removed:** `BASE_URL`, `BASE_URL_LINK` (the latter pointed at a
      `confirmations/` route deleted in T2) and the `EMAIL_*` block. All were `env()` with no
      default — i.e. **mandatory `.env` entries for values nothing read**. `.env.example` now lists
      only the 11 vars the settings actually consume, verified by booting a clean clone from it.
- [x] **T18** — **Removed a throttle that only looked enforced:** `DEFAULT_THROTTLE_RATES =
      {'login': '5/day'}` with `ScopedRateThrottle`, but **no view set `throttle_scope`**, so it was
      a no-op. Login was never rate-limited. Deleted rather than left implying protection that did
      not exist — see §9 Q14 if you want real rate limiting.
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
- **Q14** — **Login has no rate limiting.** The template's `DEFAULT_THROTTLE_RATES {'login': '5/day'}`
  was a no-op (no view set `throttle_scope`) and was removed rather than left looking enforced.
  Nothing in the assignment asks for throttling. Want real login throttling?
- **Q15** — ✅ **Answered: regenerated.** `postman-workflows.json` and `postman-variables.json` were
  rewritten against the live API: 6 folders, 50 requests, 107 assertions, verified green twice in a
  row with `npx newman run`. Tokens and ids are captured by test scripts, so nothing is pasted by
  hand. The stale `postman-workflows-usage.gif` (a
  recording of the deleted OTP flow) was deleted.
- **Q16** — **Four dead template models remain** in `apps/users`: `UserOTPVerifications`,
  `UserOTPIDVerifications`, `ChangePasswordLogs`, `ChangeEmailLogs`. Provably unused, but they own
  real tables (migrations `0002`–`0015`) and appear in the Django admin. Dropping them is a
  destructive migration, so it needs your say-so.
- **Q17** — **No token-refresh endpoint.** Login returns a refresh token, but the only thing that
  consumes it is logout (blacklisting). The assignment never specifies `/auth/refresh/`. Access
  tokens last 21 days (dev) / 1 day (prod), so nothing is broken — but the refresh token is
  otherwise inert. Add `TokenRefreshView`?
- **Q13** — **Permission codes diverge from the assignment.** The seed now uses `role.manage` and
  `permission.manage`, but the assignment's API Summary gates `POST/PATCH/DELETE /roles` on
  `role.update` and `POST/PATCH/DELETE /permissions` on `permission.update`. The API step needs to
  know which naming wins. Assumption: the newer `*.manage` codes.

---

## 9d. Full audit — DONE (commit: project audit)

Verified, not assumed. Every claim below was produced by running something.

| Area | Result |
| --- | --- |
| Imports | **100 modules imported cleanly**; no circular imports, no broken imports |
| Migrations | No conflicts; **one leaf per app** (`users.0016`, `rbac.0001`, `token_blacklist.0013`); 47 applied, 0 unapplied; `makemigrations --check` clean |
| PostgreSQL | Live on **PostgreSQL 16.14**, 20 tables; no sqlite fallback; a wrong `DB_TYPE` raises `ImproperlyConfigured` at startup |
| Swagger | 14 paths / **28 operations**, 0 errors, 0 warnings, **0 non-conforming response schemas**, every operation has a summary |
| PEP8 / ruff | `All checks passed!` (E,F,W,I,UP,B at line-length 100) |
| Tests | **453 passing** on PostgreSQL |
| Clean clone | `git archive` + `cp .env.example .env` + fill 2 values → `manage.py check` clean. Proves no setting reads a var the example omits |

**Adversarial testing (real HTTP, real JWTs):**
- Privilege escalation — all blocked: `is_staff`/`is_superuser` not writable via `PATCH /auth/profile/`;
  self-assigning a role, granting a permission, creating/deleting a role, reading the catalogue → all 403.
- Token abuse — all **401**: refresh-token-as-access, tampered signature, garbage token, `Bearer` with
  no token, wrong scheme.
- Fuzzing (21 malformed inputs: bad JSON, wrong types, 10k strings, SQL/XSS-ish, bad UUIDs, bad
  paging/ordering/filters) — **zero 5xx**, every case a clean 4xx or a correct 200.
- Full lifecycle: register → login → profile → patch → logout → refresh-reuse 400 → soft delete →
  token dead 401 → login refused 401 → **row survives with `is_active=False`**.

**Bugs found and fixed:**
- **B1** — `api/renderers.py` decided "already enveloped?" by sniffing the body for a `success` key.
  Any resource with a field of that name would silently lose the envelope, for that endpoint only.
  Now a response flag; regression-tested both ways.
- **B2** — The renderer wrapped any status < 400, including 3xx. Narrowed to 2xx.
- **B3** — `test_mock.py` asserted `len(response.data) == 3` — but `response.data` is the 3-key
  envelope, so it passed regardless of the payload. **Vacuous test**, now points at `data`.
- **B4** — `api/pagination.py`'s `get_paginated_response_schema` omitted `pages`, which the response
  actually returns: the published schema described a body the API does not send.
- **B5** — `api/exceptions.py` used `logger.exception()`, relying on ambient `sys.exc_info()`. Now
  passes `exc_info=exc` explicitly.

---

## 9c. Response envelope — DONE (commit: uniform response format)

Not in the assignment; requested separately. Every endpoint, success and failure alike, returns one
of two shapes.

- [x] **V1** — Success: `{"success": true, "message": "...", "data": {}}`.
- [x] **V2** — Failure: `{"success": false, "message": "...", "errors": {}}` (unchanged, §9b).
- [x] **V3** — Applied by `api/renderers.py::EnvelopeJSONRenderer`, wired as
      `DEFAULT_RENDERER_CLASSES`. Chosen over a per-view base class deliberately: `ModelViewSet`
      builds its own Responses, so only a renderer covers `list`/`create`/`destroy` without
      overriding each, and a new endpoint cannot forget to opt in.
- [x] **V4** — The renderer also writes back `response.data`, so `.data` and the wire agree.
      Without it `.data` would hold the bare payload while clients received the envelope — two
      answers to "what did this endpoint return", with every test asserting the one nobody gets.
- [x] **V5** — Messages: per-endpoint (`response.success_message`) or per-action for viewsets
      (`EnvelopeMessageMixin.success_messages`), falling back to a generic sentence by method+status.
- [x] **V6** — Pagination nests **inside** `data` (owner's choice): `data = {count, pages, results}`.
- [x] **V7** — ⚠️ **204/205 → 200.** HTTP forbids a body on those, so they could not carry the
      envelope. Owner's choice: `DELETE /auth/profile/`, `POST /auth/logout/`, `DELETE /roles/{id}/`
      and `DELETE /permissions/{id}/` now answer **200**. This is the one place the refactor changes
      an endpoint's contract; behaviour is otherwise untouched.
- [x] **V8** — ⚠️ The mock endpoints no longer return a bare array — it moves under `data`. That
      diverges from the assignment's literal mock example, which shows `[{...}]`. Superseded by
      "every response should follow one format".
- [x] **V9** — No double-wrapping: errors already enveloped by the exception handler pass through.
- [x] **V10** — The OpenAPI schema endpoint is **not** enveloped (it pins its own renderers);
      asserted by `test_the_openapi_schema_endpoint_is_not_enveloped`, since wrapping it would break
      Swagger UI.
- [x] **V11** — Swagger updated by `api/schema.py::envelope_responses`, a spectacular postprocessing
      hook. Views keep declaring their payload; the hook rewrites each documented body into the
      envelope, so docs and renderer cannot drift. Verified: **0 of ~60 documented responses
      non-conforming**.
- [x] **V12** — 26 tests in `src/api/tests/test_response_envelope.py` assert the wire format via
      `response.json()`; ~100 existing assertions moved to `response.data['data']`.

## 9b. Error handling — DONE (commit: exception handler)

Not in the assignment; requested separately. `src/api/exceptions.py`, wired via
`REST_FRAMEWORK['EXCEPTION_HANDLER']`.

- [x] **X1** — One envelope for every error: `{"success": false, "message": "...", "errors": {}}`.
- [x] **X2** — `ValidationError` → 400, `message = "Validation failed."`, field detail under
      `errors`. DRF's non-dict payloads (a bare list from a serializer-level error, or a plain
      string) are normalised under `non_field_errors`, because the envelope promises an object.
- [x] **X3** — `NotAuthenticated` / `AuthenticationFailed` → 401, DRF's own detail as `message`.
- [x] **X4** — `PermissionDenied` → 403, keeping the permission class's specific message
      (e.g. *"This action requires the role.view permission."*).
- [x] **X5** — `NotFound` / `Http404` → 404.
- [x] **X6** — Unhandled exceptions → 500 with a generic message. The type, message and traceback go
      to the `api.exceptions` logger and **never** to the caller. Verified over HTTP by sabotaging a
      view to raise `RuntimeError('...secret_connection_string=hunter2')`: 0 occurrences of the
      secret, the exception type, or the traceback in the response body; all present in the log.
- [x] **X7** — 405/429 and any other `APIException` ride the same envelope for free.
- [x] **X8** — **The handler reshapes `response.data` and never rebuilds the Response.** DRF decides
      401-vs-403 by whether it can build a `WWW-Authenticate` header; a handler returning a fresh
      Response would drop that header and silently downgrade every 401 to a 403. Covered by
      `test_the_401_www_authenticate_header_survives_reshaping`.
- [x] **X9** — Success responses are untouched.
- [x] **X10** — 24 dedicated tests in `src/api/tests/test_exception_handler.py`; ~33 existing
      assertions across the suite were updated to the new shape.

⚠️ **Known limitation:** the handler is DRF's, so it covers everything under `/api/v1/`. A URL that
matches no route at all never reaches DRF and still gets Django's HTML 404. Fixing that needs a
project-level `handler404` (and it only takes effect when `DEBUG=False`). Not done — flagging rather
than assuming.

⚠️ **Behaviour change:** a misconfigured `HasPermission` view used to raise `ImproperlyConfigured` out
of the request; it is now caught and reported as a logged 500. It still fails closed — the caller is
denied either way (SPEC Z7).

## 10. Process gate (per HARD CONSTRAINTS)

Every step ends with **all four**, in order:

- [ ] tests written
- [ ] `pytest` green
- [ ] `ruff` clean
- [ ] `git commit`

Postgres only — no sqlite, including in tests.
