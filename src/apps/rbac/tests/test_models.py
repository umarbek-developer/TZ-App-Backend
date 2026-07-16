import uuid

import pytest
from django.db import IntegrityError

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def role():
    return Role.objects.create(name='Manager', description='Runs a team')


@pytest.fixture
def permission():
    return Permission.objects.create(code='mock.view', name='View mock objects')


@pytest.fixture
def user():
    return User.objects.create_user(
        email='rbac@gmail.com', password='Password123!', first_name='Rbac', is_active=True
    )


# --- identifiers -------------------------------------------------------------


def test_role_and_permission_use_uuid_primary_keys(role, permission):
    assert isinstance(role.pk, uuid.UUID)
    assert isinstance(permission.pk, uuid.UUID)


def test_join_models_use_uuid_primary_keys(user, role, permission):
    user_role = UserRole.objects.create(user=user, role=role)
    role_permission = RolePermission.objects.create(role=role, permission=permission)

    assert isinstance(user_role.pk, uuid.UUID)
    assert isinstance(role_permission.pk, uuid.UUID)


def test_timestamps_are_populated(role):
    assert role.created_at is not None
    assert role.updated_at is not None


def test_updated_at_advances_on_save(role):
    original = role.updated_at

    role.description = 'Changed'
    role.save()

    role.refresh_from_db()
    assert role.updated_at > original


# --- __str__ -----------------------------------------------------------------


def test_role_str_is_its_name(role):
    assert str(role) == 'Manager'


def test_permission_str_is_its_code(permission):
    assert str(permission) == 'mock.view'


def test_user_role_str_names_both_sides(user, role):
    assert str(UserRole.objects.create(user=user, role=role)) == 'rbac@gmail.com -> Manager'


def test_role_permission_str_names_both_sides(role, permission):
    link = RolePermission.objects.create(role=role, permission=permission)

    assert str(link) == 'Manager -> mock.view'


# --- uniqueness --------------------------------------------------------------


def test_role_name_is_unique(role):
    with pytest.raises(IntegrityError):
        Role.objects.create(name='Manager')


def test_permission_code_is_unique(permission):
    with pytest.raises(IntegrityError):
        Permission.objects.create(code='mock.view', name='Duplicate')


def test_a_role_cannot_be_granted_twice_to_the_same_user(user, role):
    UserRole.objects.create(user=user, role=role)

    with pytest.raises(IntegrityError):
        UserRole.objects.create(user=user, role=role)


def test_a_permission_cannot_be_granted_twice_to_the_same_role(role, permission):
    RolePermission.objects.create(role=role, permission=permission)

    with pytest.raises(IntegrityError):
        RolePermission.objects.create(role=role, permission=permission)


# --- relationships -----------------------------------------------------------


def test_a_user_may_hold_several_roles(user):
    for name in ('Admin', 'Manager', 'Guest'):
        UserRole.objects.create(user=user, role=Role.objects.create(name=name))

    assert user.user_roles.count() == 3


def test_role_permissions_are_reachable_through_the_m2m(role, permission):
    RolePermission.objects.create(role=role, permission=permission)

    assert list(role.permissions.all()) == [permission]
    assert list(permission.roles.all()) == [role]


def test_effective_permission_codes_resolve_across_roles(user):
    """User -> roles -> permissions is the lookup the API will rely on."""
    view = Permission.objects.create(code='mock.view', name='View mock')
    edit = Permission.objects.create(code='user.update', name='Update users')

    manager = Role.objects.create(name='Manager')
    editor = Role.objects.create(name='Editor')
    RolePermission.objects.create(role=manager, permission=view)
    RolePermission.objects.create(role=editor, permission=edit)
    # Overlapping grant: the union must not double-count it.
    RolePermission.objects.create(role=editor, permission=view)

    UserRole.objects.create(user=user, role=manager)
    UserRole.objects.create(user=user, role=editor)

    codes = set(
        Permission.objects.filter(roles__user_roles__user=user).values_list('code', flat=True)
    )
    assert codes == {'mock.view', 'user.update'}


def test_a_user_with_no_roles_has_no_permissions(user):
    codes = Permission.objects.filter(roles__user_roles__user=user)

    assert not codes.exists()


# --- cascades ----------------------------------------------------------------


def test_deleting_a_role_removes_its_grants(user, role, permission):
    UserRole.objects.create(user=user, role=role)
    RolePermission.objects.create(role=role, permission=permission)

    role.delete()

    assert not UserRole.objects.exists()
    assert not RolePermission.objects.exists()
    # The user and the permission themselves must survive.
    assert User.objects.filter(pk=user.pk).exists()
    assert Permission.objects.filter(pk=permission.pk).exists()


def test_deleting_a_permission_removes_its_grants(role, permission):
    RolePermission.objects.create(role=role, permission=permission)

    permission.delete()

    assert not RolePermission.objects.exists()
    assert Role.objects.filter(pk=role.pk).exists()


def test_deleting_a_user_removes_their_role_grants(user, role):
    UserRole.objects.create(user=user, role=role)

    user.delete()

    assert not UserRole.objects.exists()
    assert Role.objects.filter(pk=role.pk).exists()
