import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import clear_permission_cache
from apps.users.models import User

PASSWORD = 'Password123!'


def make_user(email, is_active=True):
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name='T', is_active=is_active
    )


def grant(user, role_name, *codes):
    """Give `user` a role carrying `codes`, creating whatever is missing.

    Also drops the user's memoised permission set. request.user is a fresh object
    per real request, but force_authenticate pins one instance across a test's
    requests — so without this, a grant made mid-test would be invisible.
    """
    role, _ = Role.objects.get_or_create(name=role_name)
    UserRole.objects.get_or_create(user=user, role=role)
    for code in codes:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code})
        RolePermission.objects.get_or_create(role=role, permission=permission)
    clear_permission_cache(user)
    return role


def client_for(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def jwt_client_for(user):
    """A client authenticating with a real JWT, as a real caller would.

    Unlike force_authenticate — which pins the one user object it was handed for
    every request — this makes each request re-load the user from the database,
    exactly as production does. That matters for anything asserting that a
    permission change is visible immediately: with force_authenticate, the codes
    memoised on the pinned instance would mask the change.
    """
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return api


@pytest.fixture
def api():
    """Unauthenticated client."""
    return APIClient()


# Fixture roles are deliberately named Test* so they never collide with the
# Admin/Manager/Employee/Guest rows that the tests themselves create as data.


@pytest.fixture
def admin(db):
    """Holds every role.* and permission.* code — full CRUD on both resources."""
    user = make_user('admin@test.com')
    grant(user, 'TestAdmin', 'role.view', 'role.manage', 'permission.view', 'permission.manage')
    return user


@pytest.fixture
def admin_client(admin):
    return client_for(admin)


@pytest.fixture
def viewer(db):
    """Holds role.view only — reads roles, cannot write them, cannot see permissions."""
    user = make_user('viewer@test.com')
    grant(user, 'TestViewer', 'role.view')
    return user


@pytest.fixture
def viewer_client(viewer):
    return client_for(viewer)


@pytest.fixture
def permission_viewer(db):
    """Holds permission.view only — reads permissions, cannot write them."""
    user = make_user('permviewer@test.com')
    grant(user, 'TestPermissionViewer', 'permission.view')
    return user


@pytest.fixture
def permission_viewer_client(permission_viewer):
    return client_for(permission_viewer)


@pytest.fixture
def employee(db):
    """Holds no role permissions at all."""
    user = make_user('employee@test.com')
    grant(user, 'TestEmployee', 'mock.view')
    return user


@pytest.fixture
def employee_client(employee):
    return client_for(employee)


@pytest.fixture
def guest(db):
    """Holds a role, but that role carries nothing."""
    user = make_user('guest@test.com')
    grant(user, 'TestGuest')
    return user


@pytest.fixture
def guest_client(guest):
    return client_for(guest)
