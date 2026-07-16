# TZ-App-Backend

A Django REST API with JWT authentication and role-based access control (RBAC).

Seeded administrator — created by `python manage.py seed_data` (see below):

```
Email:    admin@gmail.com
Password: admin123
```

## Running locally

PostgreSQL is required — there is no SQLite fallback, and the project refuses to start without it.

```bash
cd src

# 1. Environment. .env is gitignored, so a fresh clone must create it.
cp .env.example .env
#    Then edit .env:
#      - generate SECRET_KEY:
#        python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
#      - set DB_NAME / DB_USER for your PostgreSQL
#      - leave DB_HOST empty to use the local Unix socket (peer auth, no password)

# 2. Dependencies
pip install -r requirements/dev.txt

# 3. Database
createdb tz_app
python manage.py migrate

# 4. RBAC seed data (see below)
python manage.py seed_data

# 5. Run
python manage.py runserver
```

The API is served at `http://127.0.0.1:8000/api/v1/`.

## API documentation

Generated from the code by drf-spectacular:

| URL | What |
| --- | --- |
| `/api/v1/docs/` | Swagger UI (interactive) |
| `/api/v1/redoc/` | ReDoc |
| `/api/v1/schema/` | Raw OpenAPI schema |

## Authentication

JWT, via `djangorestframework-simplejwt`. Register, then log in to receive a token pair; send the
access token on every subsequent request:

```
Authorization: Bearer <access token>
```

| Method | Endpoint | Auth | Result |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register/` | — | 201, creates an active user |
| POST | `/api/v1/auth/login/` | — | 200 `{refresh, access}` |
| POST | `/api/v1/auth/logout/` | ✅ | 205, blacklists the refresh token |
| GET | `/api/v1/auth/profile/` | ✅ | 200, the current user |
| PATCH | `/api/v1/auth/profile/` | ✅ | 200, updates the current user |
| DELETE | `/api/v1/auth/profile/` | ✅ | 204, soft delete |

**Logout** blacklists the refresh token so it can no longer mint access tokens. The access token
itself stays valid until it expires — inherent to stateless JWT.

**Delete profile** is a soft delete: `is_active` becomes `False` and the row survives. Every
outstanding refresh token for the account is blacklisted, and the current access token stops working
immediately because SimpleJWT rejects tokens belonging to inactive users. The account cannot log in
again.

## Roles

| Method | Endpoint | Permission |
| --- | --- | --- |
| GET | `/api/v1/roles/` | `role.view` |
| GET | `/api/v1/roles/{id}/` | `role.view` |
| POST | `/api/v1/roles/` | `role.manage` |
| PUT | `/api/v1/roles/{id}/` | `role.manage` |
| PATCH | `/api/v1/roles/{id}/` | `role.manage` |
| DELETE | `/api/v1/roles/{id}/` | `role.manage` |

Only the seeded **Admin** role carries `role.view`/`role.manage`, so these endpoints are
administrator-only in practice — but that follows from the RBAC tables rather than a hardcoded check,
so granting `role.view` to another role is all it takes to open up reads.

```bash
GET /api/v1/roles/?page=2&page_size=5          # pagination
GET /api/v1/roles/?search=manager              # searches name and description
GET /api/v1/roles/?ordering=-created_at        # name | created_at | updated_at, - to reverse
```

`name` is required, trimmed, at most 100 characters, and unique **case-insensitively** — `admin` is
rejected while `Admin` exists. A role's `permissions` are shown read-only; they are changed through
the assign-permission endpoint.

Deleting a role also deletes its permission grants and revokes it from everyone who held it (the
users and permissions themselves survive). Deleting the **Admin** role would strip the administrator
of every permission and lock the API — `python manage.py seed_data` restores it.

## RBAC

Authorization is driven by permissions the user holds through their roles:

```
User ──< UserRole >── Role ──< RolePermission >── Permission
```

A user may hold **several roles**, and their effective permissions are the **union** of every
permission granted to those roles. Permissions are identified by a dotted `code` such as `mock.view`;
that code is what an endpoint checks.

| Model | Key fields |
| --- | --- |
| `Role` | `name` (unique), `description` |
| `Permission` | `code` (unique), `name`, `description` |
| `UserRole` | `user`, `role` — unique together |
| `RolePermission` | `role`, `permission` — unique together |

These are the project's own tables and have nothing to do with `django.contrib.auth`'s permission
system.

### How permissions are checked

1. The request arrives with `Authorization: Bearer <access>`.
2. SimpleJWT validates the token's signature and expiry, and rejects it if the user is inactive.
   No/invalid token → **401 Unauthorized**.
3. The endpoint resolves the user's permission codes by walking
   `User → UserRole → Role → RolePermission → Permission.code`.
4. If the required code is missing from that set → **403 Forbidden**.

The 401/403 split is deliberate: **401** means *we do not know who you are*; **403** means *we know
who you are and you may not do this*.

In code — helpers in `apps/rbac/services.py`, permission classes in `apps/rbac/permissions.py`:

```python
from apps.rbac.permissions import HasPermission, require_permissions

class MockProjectsView(APIView):
    permission_classes = [require_permissions('mock.view')]

class RoleListView(APIView):                 # equivalent, declared on the view
    permission_classes = [HasPermission]
    required_permissions = 'role.view'

require_permissions('role.view', 'role.manage')                    # needs both
require_permissions('role.view', 'role.manage', require_all=False)  # needs either
```

```python
from apps.rbac.services import get_user_permission_codes, user_has_permission

user_has_permission(request.user, 'mock.view')   # -> bool
get_user_permission_codes(request.user)          # -> frozenset of codes
```

Resolving a user's permissions costs **one query** however many roles they hold, and the result is
memoised on the user instance for the rest of the request. `is_superuser` is not consulted.

## Seed command

```bash
cd src
python manage.py seed_data
```

Creates four roles, eight permissions, the grants between them, and the administrator account.
**Idempotent** — running it any number of times reuses existing rows and never creates duplicates.

Roles and their permissions after seeding:

| Role | Permissions |
| --- | --- |
| **Admin** | all eight |
| **Manager** | `mock.view`, `user.view` |
| **Employee** | `mock.view` |
| **Guest** | none |

The eight permission codes: `user.view`, `user.update`, `user.delete`, `role.view`, `role.manage`,
`permission.view`, `permission.manage`, `mock.view`.

The command also creates `admin@gmail.com` / `admin123` as a superuser **and grants it the Admin
role**. That grant is what gives the account its power: authorization is decided purely by the RBAC
tables, and `is_superuser` confers no API permissions on its own — a superuser holding no roles is
denied every permission-gated endpoint. If the account already exists, the command leaves its
password alone and only ensures the flags and the role.

The catalogue in `apps/rbac/management/commands/seed_data.py` is the source of truth: re-running the
command restores any role/permission description that was edited elsewhere, and re-creates any
declared grant that was removed.

By default the command only ever **adds** grants, so a permission granted by hand is never silently
revoked. To reconcile exactly to the declared catalogue and drop undeclared grants:

```bash
python manage.py seed_data --prune
```

## Development

Both tools run from the repository root:

```bash
pytest              # requires PostgreSQL; creates test_<DB_NAME>
ruff check .
```

## Project layout

```
src/
  api/            HTTP layer — routing, views, serializers. Not Django apps.
    auth/         authentication endpoints
    user/         end-user endpoints
    admin/        staff endpoints
  apps/           Django apps — models and migrations
    users/        the custom User model
    rbac/         Role, Permission, UserRole, RolePermission
    utils/        shared model primitives
  config/         settings (split base/development/production), urls, wsgi/asgi
  requirements/   common.txt <- dev.txt / production.txt
```
