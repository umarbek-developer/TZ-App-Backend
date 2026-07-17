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
| POST | `/api/v1/auth/login/` | — | 200, `data` = `{refresh, access}` |
| POST | `/api/v1/auth/logout/` | ✅ | 200, blacklists the refresh token |
| GET | `/api/v1/auth/profile/` | ✅ | 200, the current user |
| PATCH | `/api/v1/auth/profile/` | ✅ | 200, updates the current user |
| DELETE | `/api/v1/auth/profile/` | ✅ | 200, soft delete |

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

## Permissions

| Method | Endpoint | Permission |
| --- | --- | --- |
| GET | `/api/v1/permissions/` | `permission.view` |
| GET | `/api/v1/permissions/{id}/` | `permission.view` |
| POST | `/api/v1/permissions/` | `permission.manage` |
| PUT | `/api/v1/permissions/{id}/` | `permission.manage` |
| PATCH | `/api/v1/permissions/{id}/` | `permission.manage` |
| DELETE | `/api/v1/permissions/{id}/` | `permission.manage` |

As with roles, only the seeded **Admin** role carries these codes, so the catalogue is
administrator-only in practice without that being hardcoded.

**Filtering** is precise, unlike `?search=` which loosely matches code, name and description:

```bash
GET /api/v1/permissions/?code=mock.view          # exact, case-insensitive
GET /api/v1/permissions/?code_contains=manage    # substring
GET /api/v1/permissions/?namespace=user          # everything under user.*
GET /api/v1/permissions/?name=mock               # substring of the display name
GET /api/v1/permissions/?role_name=Manager       # what a role holds
GET /api/v1/permissions/?role=<role-uuid>
GET /api/v1/permissions/?unassigned=true         # granted by no role
GET /api/v1/permissions/?created_after=2026-01-01T00:00:00Z
GET /api/v1/permissions/?search=deactivate       # loose, across three columns
GET /api/v1/permissions/?ordering=-code          # code | name | created_at | updated_at
```

`code` is **lowercased on write** and must be lowercase words joined by `.`, `_` or `-` — posting
`Report.Export` stores `report.export`. This is not cosmetic: permission checks compare codes by
exact string, so a stored `Report.Export` could never match a `report.export` check. Codes are unique
case-insensitively.

Deleting a permission revokes it from every role that held it; the roles survive. Any endpoint gated
on the deleted code then denies everyone — `seed_data` restores the catalogue.

## Assigning roles to users

One endpoint, three operations, split by HTTP verb. All require `role.manage`.

| Method | Endpoint | Does |
| --- | --- | --- |
| POST | `/api/v1/assign-role/` | **Adds** roles, keeping the ones already held |
| PUT | `/api/v1/assign-role/` | **Replaces** — the user ends up with exactly the listed roles |
| DELETE | `/api/v1/assign-role/` | **Removes** the listed roles, leaving the rest |

All three take the same body:

```json
{ "user": "<user-uuid>", "roles": ["<role-uuid>", "<role-uuid>"] }
```

and answer with the resulting state plus what changed:

```json
{
  "user": { "id": "…", "email": "john@x.com", "full_name": "John Doe", "is_active": true },
  "roles": ["Employee", "Manager"],
  "added": ["Employee"],
  "already_assigned": ["Manager"]
}
```

PUT reports `added` / `removed` / `unchanged`; DELETE reports `removed` / `not_assigned`.

**Idempotent.** Assigning a role the user already holds, or removing one they never had, is a no-op
reported in the response rather than an error — so retries are safe.

**Validation.** The user and every role must exist, ids may not repeat within one request, and
`roles` may not be empty (except on PUT, where an empty list is how you strip every role). A single
unknown id rejects the whole request: the writes are transactional, so a half-valid payload lands
nothing.

## Assigning permissions to roles

Same shape, one level up the chain. All require `permission.manage`.

| Method | Endpoint | Does |
| --- | --- | --- |
| POST | `/api/v1/assign-permission/` | **Adds** permissions, keeping the ones already carried |
| PUT | `/api/v1/assign-permission/` | **Replaces** — the role ends up carrying exactly the listed permissions |
| DELETE | `/api/v1/assign-permission/` | **Removes** the listed permissions, leaving the rest |

```json
{ "role": "<role-uuid>", "permissions": ["<permission-uuid>", "<permission-uuid>"] }
```

```json
{
  "role": { "id": "…", "name": "Guest" },
  "permissions": ["mock.view", "role.view"],
  "added": ["role.view"],
  "already_assigned": ["mock.view"]
}
```

PUT reports `added` / `removed` / `unchanged`; DELETE reports `removed` / `not_assigned`. Idempotent
and validated exactly as assign-role above.

### Changes take effect immediately

Every user holding the role sees the change on their **very next request** — no re-login, no token
refresh, no cache to wait out:

```
GET /api/v1/roles/   with a Guest's token        -> 403
POST /api/v1/assign-permission/  grant role.view to Guest
GET /api/v1/roles/   same token, unchanged       -> 200
DELETE /api/v1/assign-permission/  revoke it
GET /api/v1/roles/   same token, unchanged       -> 403
```

This is a property of the design rather than an extra mechanism: permission codes are read from the
database on each request and memoised only for that request's lifetime, so there is no stale state
to invalidate across requests. The JWT carries identity, never permissions — which is exactly why a
token issued before the grant still picks it up.

## Response format

**Every** response from every endpoint uses one of two envelopes, and nothing else.

Success:

```json
{ "success": true, "message": "Roles retrieved successfully.", "data": { } }
```

Failure:

```json
{ "success": false, "message": "Validation failed.", "errors": { "name": ["This field may not be blank."] } }
```

`success` tells a client which shape it is holding without inspecting the status code. `data` is the
payload — an object, an array, or `{}` when there is nothing to return. `errors` carries field-scoped
detail and is `{}` for failures with no per-field breakdown. The two never mix: a success body has no
`errors` key, a failure body has no `data` key.

List endpoints keep their pagination **inside** `data`:

```json
{
  "success": true,
  "message": "Roles retrieved successfully.",
  "data": { "count": 4, "pages": 1, "results": [ {"id": "…", "name": "Admin"} ] }
}
```

Applied by `api/renderers.py` (successes) and `api/exceptions.py` (failures) — not by individual
views, so DRF's own generic machinery is covered by the same rule and a new endpoint cannot forget it.

### Deletes and logout answer 200, not 204

HTTP forbids a body on `204`/`205`, so those four endpoints would have been the one exception to the
format. They return **200** with the envelope instead:

```json
{ "success": true, "message": "Role deleted successfully.", "data": {} }
```

Affects `DELETE /auth/profile/`, `POST /auth/logout/`, `DELETE /roles/{id}/`, `DELETE
/permissions/{id}/`. Nothing else about them changed.

## Error responses

`message` is a human-readable sentence; `errors` carries the field-scoped detail.

| Situation | Status | `message` | `errors` |
| --- | --- | --- | --- |
| No or invalid token | 401 | `Authentication credentials were not provided.` | `{}` |
| Authenticated, permission missing | 403 | `This action requires the role.view permission.` | `{}` |
| Validation failed | 400 | `Validation failed.` | `{"name": ["This field may not be blank."]}` |
| Unknown id | 404 | `No Role matches the given query.` | `{}` |
| Wrong method | 405 | `Method "POST" not allowed.` | `{}` |
| Unhandled exception | 500 | `Internal server error.` | `{}` |

Implemented in `api/exceptions.py`, wired via `REST_FRAMEWORK['EXCEPTION_HANDLER']`.

**A 500 never leaks internals.** The exception message, its type and the traceback go to the logger
under `api.exceptions`; the caller only ever sees the generic sentence above. That makes the log the
*only* record of a crash — keep logging configured in production.

Successful responses are untouched: the envelope applies to errors only.

## Mock business resources

Stand-ins for real business objects, used to show RBAC gating ordinary endpoints. **No database
tables** — the payloads are static constants, and the responses are bare JSON arrays.

| Method | Endpoint | Permission |
| --- | --- | --- |
| GET | `/api/v1/mock/projects/` | `mock.view` |
| GET | `/api/v1/mock/orders/` | `mock.view` |
| GET | `/api/v1/mock/employees/` | `mock.view` |
| GET | `/api/v1/mock/documents/` | `mock.view` |

```bash
GET /api/v1/mock/projects/
[{"id": 1, "name": "CRM"}, {"id": 2, "name": "ERP"}]

GET /api/v1/mock/orders/
[{"id": 100, "price": 500}]
```

These are the endpoints a **non-administrator** can actually reach, so they are the clearest
demonstration of the RBAC rules. With the seeded data:

| Caller | Result |
| --- | --- |
| Anonymous | **401** |
| Guest (role with no permissions) | **403** |
| Employee (`mock.view`) | **200** |
| Manager (`mock.view`, `user.view`) | **200** |
| Admin (all eight) | **200** |



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

## Postman

`postman-workflows.json` + `postman-variables.json` exercise the whole API.

1. Import `postman-variables.json` as an **environment** and select it.
2. Import `postman-workflows.json` as a **collection**.
3. Run **1. Auth > Login (admin)** — it stores the token pair; every admin request picks it up
   automatically via collection-level bearer auth.

Or run the lot headless:

```bash
npx newman run src/postman-workflows.json -e src/postman-variables.json
```

Six folders, 50 requests, 107 assertions — each folder captures the ids the next needs (role_id,
permission_id, demo_user_id…), so the collection runs top-to-bottom with nothing pasted by hand, and
is safe to re-run. Folder 6 demonstrates the 401/403/404/405 rules directly.

## Development

Both tools run from the repository root:

```bash
pytest              # requires PostgreSQL; creates test_<DB_NAME>
ruff check .
```

## Project layout

```
src/
  api/                  HTTP layer — routing, views, serializers. Not Django apps.
    auth/               register, login, logout, profile
    user/               roles, permissions, assign-role, assign-permission, mock
    exceptions.py       error envelope   -> REST_FRAMEWORK['EXCEPTION_HANDLER']
    renderers.py        success envelope -> DEFAULT_RENDERER_CLASSES
    schema.py           Swagger envelope -> SPECTACULAR POSTPROCESSING_HOOKS
    pagination.py       CustomPagination -> DEFAULT_PAGINATION_CLASS
  apps/                 Django apps — models and migrations
    users/              the custom User model
    rbac/               Role/Permission/UserRole/RolePermission, services,
                        permission classes, seed_data command
  config/               settings (base/development/production), urls, wsgi/asgi
  requirements/         common.txt <- dev.txt / production.txt
```
