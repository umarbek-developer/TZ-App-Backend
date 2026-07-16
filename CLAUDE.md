# CLAUDE.md

> ## ⚠️ STATUS: Section A is SUPERSEDED (decision of 2026-07-16)
>
> The assignment ([docs/assignment.md](docs/assignment.md)) mandates the exact stack Section A
> forbids, and the project owner resolved the conflict **in favour of the assignment**. The
> instruction was: *"Implement complete authentication using Django REST Framework and SimpleJWT"*,
> *"blacklist refresh token"*, and *"The Custom User model is already implemented. DO NOT recreate
> models."*
>
> Section A is kept verbatim below as the historical record. **What actually governs the code:**
>
> | Section A said | What is built |
> | --- | --- |
> | Auth from scratch, no DRF built-ins | `djangorestframework-simplejwt` + DRF `IsAuthenticated` |
> | PyJWT HS256, hand-rolled | SimpleJWT (which uses PyJWT HS256 underneath) |
> | Logout ⇒ own `revoked_tokens` table | SimpleJWT `token_blacklist` app |
> | bcrypt directly, never Django hashers | Django pbkdf2 via `set_password()` — the existing `User` requires it |
> | No `AbstractUser` | `apps.users.User` keeps `AbstractUser` |
>
> **Still in force from Section A:** not identified ⇒ 401, identified but forbidden ⇒ 403;
> PostgreSQL only; every step ends with tests written, pytest green, ruff clean, git commit.

## A. HARD CONSTRAINTS (superseded — see status note above)

- Auth/authz are built FROM SCRATCH. Forbidden in the API request path: django.contrib.auth models (User, AbstractUser, AbstractBaseUser, Permission, Group), its middleware/backends, login()/logout()/authenticate(), @login_required, DRF built-in authentication classes (Session/Basic/TokenAuthentication) and permission classes (IsAuthenticated, IsAdminUser, DjangoModelPermissions). Subclassing DRF BaseAuthentication/BasePermission with fully custom logic IS allowed.
- Passwords hashed with bcrypt directly (never Django hashers).
- Tokens: PyJWT HS256, payload {user_id, jti, iat, exp}. Logout = insert jti into revoked_tokens. Custom middleware parses "Authorization: Bearer <jwt>", validates signature/exp/jti-not-revoked/user.is_active, sets request.user = our User or None.
- Not identified -> 401. Identified but rule forbids -> 403.
- Postgres only. Every step ends with: tests written, pytest green, ruff clean, git commit.

## B. PROJECT CONVENTIONS

### Repository shape

The Django project root is `src/`, not the repo root. `manage.py` lives at `src/manage.py`, and every
relative path in the settings resolves from `src/`. `BASE_DIR` is computed in
`src/config/settings/base.py` as three `dirname()` calls up from that file, which lands on `src/` —
so `BASE_DIR` is `src/`, *not* the repo root. Anything reading `BASE_DIR` (`.env`, `media/`,
`static/`) is therefore rooted at `src/`.

The repo root holds only `README.md`, `.gitignore`, `deployment/`, and this file.

### Where Django apps live: `apps/` vs `api/`

These two trees are **not** parallel — they are two different layers, and only one of them contains
Django apps.

**`src/apps/<name>/` — the Django apps (the only things in `INSTALLED_APPS`).**
Each has `apps.py`, `models.py`, `migrations/`, `admin.py`, `tests.py`. These own persistence and
domain logic. They are registered in `INSTALLED_APPS` under their dotted path *including* the `apps.`
prefix — `'apps.users'`, `'apps.utils'` — because `src/` is the import root, not `src/apps/`.
There is no `apps` package-level `AppConfig`; the label Django infers is the last segment
(`users`, `utils`), which is why `AUTH_USER_MODEL` reads `'users.User'` and not `'apps.users.User'`.

`apps/utils/` is the shared-primitives app: `BaseModel` (created_by/updated_by/deleted_by/is_deleted
/created_at/updated_at, `abstract = True`) plus a `management/commands/` slot. It has no migrations
of its own.

**`src/api/<audience>/` — the HTTP layer. NOT Django apps.**
None of `api/`, `api/admin/`, `api/auth/`, `api/user/` contain an `apps.py`, none contain models, and
none appear in `INSTALLED_APPS`. They are plain Python packages holding routing and request/response
code, sliced by **audience** rather than by domain:

- `api/auth/` — unauthenticated + self-service account endpoints
- `api/user/` — end-user endpoints (currently an empty router stub)
- `api/admin/` — staff endpoints (note: this is the *API* admin surface, unrelated to
  `django.contrib.admin`, which is mounted separately at `/admin/`)

Each audience package follows the same fixed layout:

```
api/<audience>/
  urls.py            # path() list for this audience
  views/             # one module per use case, e.g. login_views.py
  serializers/       # one module per resource, e.g. user_serializers.py
  permissions.py
  exceptions.py
  filters.py
  helpers.py
  tests.py
```

Cross-audience shared HTTP pieces sit at the `api/` top level: `api/pagination.py`
(`CustomPagination`, wired as the DRF default), `api/serializers.py`, `api/views.py`.

**Import direction is one-way:** `api/` imports from `apps/`; `apps/` must never import from `api/`.

**URL mounting:** `config/urls.py` mounts `api.urls` at `/api/v1/`; `api/urls.py` mounts
`api.admin.urls` at `admin/`, `api.user.urls` at `user/`, and `api.auth.urls` at the root. So a login
route declared as `auth/login/` in `api/auth/urls.py` is served at `/api/v1/auth/login/`.

**Rule of thumb for new code:** a model or migration goes in `src/apps/<domain>/`; a URL, view, or
serializer goes in `src/api/<audience>/`. Anything with a model needs its app added to
`INSTALLED_APPS` as `'apps.<domain>'`.

**Placement directives for this assignment** (these override the assignment's own proposed
`rbac_backend/apps/{accounts,rbac,mock}/` tree, which bundles models+views+serializers per app and
does not match this template):

| Concern | Goes in |
| --- | --- |
| Models | `src/apps/` — new apps `apps.accounts`, `apps.rbac` |
| Serializers | `src/api/user/serializers/` |
| Views | `src/api/user/views/` |
| Backend URLs | `src/api/user/urls.py` |
| Main API urlconf | `src/api/urls.py` (aggregator) |

The backend belongs **inside `api/`**. `mock` needs no models at all ("No database needed" — return
static JSON), so it exists only as views + a permission check, with nothing under `apps/`.

### How the settings split works, and where env vars load

`DJANGO_SETTINGS_MODULE` is `config.settings` (set in `manage.py`, `wsgi.py`, `asgi.py`) — it points
at the **package**, so `src/config/settings/__init__.py` is the entrypoint. It is a dispatcher, not a
settings file:

```
config/settings/__init__.py   # reads .env, then branches on DEBUG
    -> development.py         # DEBUG truthy
    -> production.py          # DEBUG falsy
        both start with: from .base import *
```

`__init__.py` calls `environ.Env.read_env(BASE_DIR/.env)`, which loads `src/.env` into `os.environ`,
then reads `int(os.environ.get("DEBUG", 1))` and imports `development` or `production` accordingly.
It also prints which branch it took. **Default is development** — an absent `DEBUG` means dev.

`base.py` holds everything shared and re-runs `read_env(BASE_DIR/.env)` itself (the load happens
twice; harmless but worth knowing). Every env var is read there through django-environ's
`env("NAME")` — `SECRET_KEY`, `DEBUG`, `BASE_URL`, `BASE_URL_LINK`, `DB_*`, `EMAIL_HOST`,
`EMAIL_PASSWORD`. `env("NAME")` with no default **raises `ImproperlyConfigured` if the var is
missing**, so a var added to `base.py` must also be added to `src/.env.example`.

Two env-var quirks to respect:

- `base.py` re-reads `DEBUG` as a **string** and compares `DEBUG == "1"`, while `__init__.py` casts
  it with `int()`. Both must agree; `DEBUG=1` / `DEBUG=0` are the only safe values.
- Env-var-dependent settings are split by branch. `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and
  `CORS_ALLOWED_ORIGINS` are read **only in `production.py`** — those three vars are unused in dev
  (dev hardcodes `ALLOWED_HOSTS = ['*']` and allow-all CORS).

`src/.env` is **gitignored and not in the repo**. `src/.env.example` is the tracked template; a fresh
clone must `cp src/.env.example src/.env` before anything runs.

### Which requirements file a new dependency belongs in

Requirements live at **`src/requirements/`** (under `src/`, not the repo root), and chain:

| File | Contents | Use for |
| --- | --- | --- |
| `common.txt` | the real dependency list | anything imported by app code at runtime |
| `dev.txt` | `-r common.txt` | local-only tooling (test runners, linters) |
| `production.txt` | `-r common.txt` + `gunicorn` | prod-only serving deps |

So: **runtime dep -> `common.txt`** (it reaches dev and prod through the `-r` chain).
**Tooling that must never ship to prod -> `dev.txt`.**

Concretely, for this project: `bcrypt`, `PyJWT`, `psycopg2-binary` go in `common.txt`;
`pytest`, `pytest-django`, `ruff` go in `dev.txt`.

Two live gotchas:

- `common.txt` is encoded **UTF-16LE with a BOM and CRLF line endings**, unlike the other two
  (ASCII). pip 24.0 parses it correctly (verified), so it is not currently broken — but any tool that
  assumes UTF-8, and any naive `>>` append from a shell, will corrupt it. Normalize it to UTF-8
  before editing.
- Nothing is version-pinned. A fresh install resolves to latest (currently Django 6.0.7).

### How the server runs locally

Per `src/qollanma.md` (**never modify that file**), plus the `.env` step it omits:

```bash
cd src
cp .env.example .env           # required: .env is gitignored; without it env("SECRET_KEY") raises ImproperlyConfigured
# then edit .env: generate a SECRET_KEY, set DB_NAME/DB_USER for your PostgreSQL
pip install -r requirements/dev.txt
createdb tz_app                # PostgreSQL is mandatory; there is no sqlite fallback
python manage.py migrate
python manage.py runserver
```

`DB_TYPE` must be `psql` or `base.py` raises `ImproperlyConfigured` at startup — deliberately, so a
misconfigured environment fails loudly instead of silently running on a different database. Leave
`DB_HOST` empty to use the local Unix socket (peer auth, no password); a TCP host needs `DB_PASSWORD`.

All commands run from `src/`. No settings flag is needed — `manage.py` sets
`DJANGO_SETTINGS_MODULE=config.settings` and the `DEBUG` value in `.env` selects the dev/prod branch.
The API is then at `http://127.0.0.1:8000/api/v1/`, with interactive docs at `/api/v1/docs/`
(Swagger UI), `/api/v1/redoc/`, and the raw OpenAPI schema at `/api/v1/schema/`.

Postman collections for manual API exercise: `src/postman-workflows.json` +
`src/postman-variables.json` (usage walkthrough in `src/postman-workflows-usage.gif`).

Production is served by gunicorn via `deployment/gunicorn.service` + `gunicorn.socket` behind
`deployment/nginx.conf`.

### Testing and linting

Both are configured in the repo-root `pyproject.toml` and **run from the repo root**, not `src/`:

```bash
pytest                 # pythonpath=["src"], DJANGO_SETTINGS_MODULE=config.settings
ruff check .           # must report "All checks passed!"
ruff check . --fix     # applies the safe fixes
```

Tests need a reachable PostgreSQL and a role with CREATEDB (pytest-django creates `test_<DB_NAME>`).

Tests live in a `tests/` package inside the relevant `api/<audience>/` package, one module per use
case (`test_register.py`, `test_login.py`, …) with shared fixtures in `tests/conftest.py`. Note the
package form: a legacy `tests.py` in the same directory would collide with a `tests/` package, so
delete the stub when adding the package.

`ruff` is configured with `E,F,W,I,UP,B` at line-length 100, excluding migrations. The settings
package is exempt from `F403/F405` because `from .base import *` is deliberate there.

### Conventions to preserve

- Uzbek-language comments are normal in this codebase; match the surrounding file's language.
- Views are one class per file under `views/`, named `<usecase>_views.py`.
- `User.id` is a `UUIDField` primary key (`default=uuid.uuid4`), not an integer — carry this into the
  from-scratch `User`, and note the JWT `user_id` claim must be serialized as a string.
