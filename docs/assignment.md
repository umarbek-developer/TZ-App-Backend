> Assignment as provided, verbatim and unedited. Do not "fix" this file — it is the source of
> record. Interpretation, conflict resolution, and derived requirements belong in `SPEC.md`.
>
> Two provenance notes:
> - Provided as English Markdown (the original instruction described it as Russian PDF text).
> - The placement directives that accompanied the paste ("backend should be inside the api",
>   `api/user/serializers` => serializers, `api/user/views` => views, `src/apps` => models,
>   `api/urls.py` => main urls, `api/user/urls.py` => backend urls) were separate instructions
>   rather than assignment body, so they are recorded in `CLAUDE.md` and `SPEC.md` instead of here.

---

Project Structure

```text
rbac_backend/
├── apps/
│   ├── accounts/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── permissions.py
│   │   ├── urls.py
│   │   └── services.py
│   │
│   ├── rbac/
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services.py
│   │
│   └── mock/
│       ├── views.py
│       ├── urls.py
│       └── permissions.py
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── jwt.py
│
├── requirements.txt
├── README.md
└── manage.py
```

---

# Database Design

## User

```python
id
first_name
last_name
middle_name
email (unique)
password
is_active
is_staff
is_superuser
created_at
updated_at
```

---

## Role

```python
id
name
description
```

Examples

```
Admin
Manager
Employee
Guest
```

---

## Permission

```python
id
code
name
description
```

Examples

```
user.view
user.create
user.update
user.delete

mock.view

role.view
role.update

permission.view
permission.update
```

---

## RolePermission

Many-to-many

```python
role
permission
```

---

## UserRole

Many-to-many

```python
user
role
```

A user may have several roles.

---

# Authentication

Use

```
djangorestframework-simplejwt
```

Endpoints

```
POST /api/auth/register/

POST /api/auth/login/

POST /api/auth/logout/

GET /api/auth/profile/

PATCH /api/auth/profile/

DELETE /api/auth/profile/
```

Soft delete

```python
user.is_active = False
```

After deletion

```
Logout

JWT becomes invalid

Cannot login again
```

---

# Authentication Flow

Registration

↓

Login

↓

Receive JWT

↓

Authorization Header

```
Bearer eyJhb...
```

↓

Authenticated requests

---

# Authorization

JWT Authentication

401

If token missing

```
Unauthorized
```

403

If authenticated but permission missing

```
Forbidden
```

---

# RBAC Flow

```
User

↓

Roles

↓

Permissions

↓

Endpoint
```

Example

```
User

↓

Manager

↓

mock.view

↓

GET /mock/projects/
```

Allowed

---

Another user

↓

Guest

↓

No permission

↓

403 Forbidden

---

# Required APIs

## Registration

POST

```
/api/auth/register/
```

Request

```json
{
    "first_name":"John",
    "last_name":"Doe",
    "middle_name":"Smith",
    "email":"john@gmail.com",
    "password":"Password123!",
    "confirm_password":"Password123!"
}
```

---

## Login

```
POST
```

```json
{
    "email":"john@gmail.com",
    "password":"Password123!"
}
```

Response

```json
{
    "refresh":"",
    "access":""
}
```

---

## Logout

Blacklist Refresh Token

```
POST
```

---

## Profile

```
GET
```

Current user

---

## Update

```
PATCH
```

---

## Delete

```
DELETE
```

Implementation

```python
request.user.is_active=False
request.user.save()
```

---

# Admin APIs

## Roles

```
GET

POST

PATCH

DELETE
```

---

## Permissions

```
GET

POST

PATCH

DELETE
```

---

## Assign Role

```
POST
```

```json
{
    "user":1,
    "roles":[2,3]
}
```

---

## Assign Permission

```
POST
```

```json
{
    "role":2,
    "permissions":[5,6,7]
}
```

---

# Mock Business Objects

No database needed.

Simply return JSON.

Example

```
GET

/api/mock/projects/
```

Response

```json
[
    {
        "id":1,
        "name":"CRM"
    },
    {
        "id":2,
        "name":"ERP"
    }
]
```

Permission required

```
mock.view
```

---

Another endpoint

```
GET

/api/mock/orders/
```

Returns

```json
[
    {
        "id":100,
        "price":500
    }
]
```

Permission

```
mock.view
```

---

# Permission Decorator

Every endpoint checks

```
Is user authenticated?

↓

401
```

↓

Has permission?

↓

403

↓

Return resource

---

# Seed Data

Administrator

```
admin@mail.com

password123
```

Roles

```
Admin

Manager

Employee

Guest
```

Permissions

```
user.view

user.update

user.delete

mock.view

role.view

role.update

permission.view

permission.update
```

Admin receives

All permissions

Manager

```
mock.view
user.view
```

Employee

```
mock.view
```

Guest

None

---

# README Should Explain

```
Authentication

↓

JWT

↓

RBAC

↓

Roles

↓

Permissions

↓

How permissions are checked

↓

How to run

↓

PostgreSQL setup

↓

Seed command

↓

API documentation
```

---

# Packages

```txt
Django
djangorestframework
psycopg2-binary
djangorestframework-simplejwt
django-filter
drf-spectacular
python-decouple
Pillow
```

---

# API Summary

| Method | Endpoint           | Auth | Permission        |
| ------ | ------------------ | ---- | ----------------- |
| POST   | /auth/register     | ❌    | Public            |
| POST   | /auth/login        | ❌    | Public            |
| POST   | /auth/logout       | ✅    | Authenticated     |
| GET    | /auth/profile      | ✅    | Authenticated     |
| PATCH  | /auth/profile      | ✅    | Authenticated     |
| DELETE | /auth/profile      | ✅    | Authenticated     |
| GET    | /roles             | ✅    | role.view         |
| POST   | /roles             | ✅    | role.update       |
| PATCH  | /roles/{id}        | ✅    | role.update       |
| DELETE | /roles/{id}        | ✅    | role.update       |
| GET    | /permissions       | ✅    | permission.view   |
| POST   | /permissions       | ✅    | permission.update |
| PATCH  | /permissions/{id}  | ✅    | permission.update |
| DELETE | /permissions/{id}  | ✅    | permission.update |
| POST   | /assign-role       | ✅    | role.update       |
| POST   | /assign-permission | ✅    | permission.update |
| GET    | /mock/projects     | ✅    | mock.view         |
| GET    | /mock/orders       | ✅    | mock.view         |
