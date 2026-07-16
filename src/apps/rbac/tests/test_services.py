import pytest

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import (
    clear_permission_cache,
    get_user_permission_codes,
    get_user_role_names,
    get_user_roles,
    user_has_all_permissions,
    user_has_any_permission,
    user_has_permission,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


def make_user(email='rbac@gmail.com', is_active=True):
    return User.objects.create_user(
        email=email, password='Password123!', first_name='R', is_active=is_active
    )


def grant(user, role_name, *codes):
    role, _ = Role.objects.get_or_create(name=role_name)
    UserRole.objects.get_or_create(user=user, role=role)
    for code in codes:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code})
        RolePermission.objects.get_or_create(role=role, permission=permission)
    return role


@pytest.fixture
def user():
    return make_user()


# --- resolution --------------------------------------------------------------


def test_user_with_no_roles_has_no_permissions(user):
    assert get_user_permission_codes(user) == frozenset()


def test_role_with_no_permissions_grants_nothing(user):
    grant(user, 'Guest')

    assert get_user_permission_codes(user) == frozenset()


def test_permissions_resolve_through_a_role(user):
    grant(user, 'Employee', 'mock.view')

    assert get_user_permission_codes(user) == {'mock.view'}


def test_permissions_union_across_multiple_roles(user):
    grant(user, 'Employee', 'mock.view')
    grant(user, 'Manager', 'user.view')

    assert get_user_permission_codes(user) == {'mock.view', 'user.view'}


def test_overlapping_roles_do_not_duplicate_codes(user):
    grant(user, 'Employee', 'mock.view')
    grant(user, 'Manager', 'mock.view', 'user.view')

    # A frozenset collapses duplicates; assert the count too so a regression to a
    # list would be caught.
    codes = get_user_permission_codes(user)
    assert codes == {'mock.view', 'user.view'}
    assert len(codes) == 2


def test_permissions_are_not_leaked_between_users(user):
    other = make_user('other@gmail.com')
    grant(user, 'Employee', 'mock.view')
    grant(other, 'Manager', 'user.delete')

    assert get_user_permission_codes(user) == {'mock.view'}
    assert get_user_permission_codes(other) == {'user.delete'}


def test_revoking_a_role_revokes_its_permissions(user):
    role = grant(user, 'Employee', 'mock.view')

    UserRole.objects.filter(user=user, role=role).delete()

    clear_permission_cache(user)
    assert get_user_permission_codes(user) == frozenset()


# --- ineligible callers ------------------------------------------------------


def test_inactive_user_holds_nothing(user):
    grant(user, 'Admin', 'user.delete')
    user.is_active = False

    clear_permission_cache(user)
    assert get_user_permission_codes(user) == frozenset()


def test_none_holds_nothing():
    assert get_user_permission_codes(None) == frozenset()
    assert user_has_permission(None, 'mock.view') is False


def test_anonymous_holds_nothing():
    class Anon:
        is_authenticated = False
        is_active = False

    assert get_user_permission_codes(Anon()) == frozenset()


# --- helper predicates -------------------------------------------------------


def test_user_has_permission(user):
    grant(user, 'Employee', 'mock.view')

    assert user_has_permission(user, 'mock.view') is True
    assert user_has_permission(user, 'user.delete') is False


def test_user_has_all_permissions(user):
    grant(user, 'Manager', 'mock.view', 'user.view')

    assert user_has_all_permissions(user, ['mock.view', 'user.view']) is True
    assert user_has_all_permissions(user, ['mock.view', 'user.delete']) is False


def test_user_has_all_permissions_is_true_for_an_empty_requirement(user):
    assert user_has_all_permissions(user, []) is True


def test_user_has_any_permission(user):
    grant(user, 'Employee', 'mock.view')

    assert user_has_any_permission(user, ['mock.view', 'user.delete']) is True
    assert user_has_any_permission(user, ['user.view', 'user.delete']) is False


def test_user_has_any_permission_is_false_for_an_empty_requirement(user):
    grant(user, 'Admin', 'mock.view')

    # "any of nothing" is false — the opposite of all-of-nothing.
    assert user_has_any_permission(user, []) is False


# --- roles -------------------------------------------------------------------


def test_get_user_roles(user):
    grant(user, 'Employee', 'mock.view')
    grant(user, 'Manager', 'user.view')

    assert get_user_role_names(user) == {'Employee', 'Manager'}
    assert get_user_roles(user).count() == 2


def test_get_user_roles_is_empty_for_anonymous():
    assert not get_user_roles(None).exists()
    assert get_user_role_names(None) == frozenset()


# --- query efficiency --------------------------------------------------------


def test_resolution_is_a_single_query_regardless_of_role_count(user, django_assert_num_queries):
    grant(user, 'Employee', 'mock.view')
    grant(user, 'Manager', 'user.view', 'user.update')
    grant(user, 'Admin', 'role.view', 'role.manage', 'permission.view')

    clear_permission_cache(user)
    with django_assert_num_queries(1):
        codes = get_user_permission_codes(user)

    assert len(codes) == 6


def test_repeat_lookups_hit_the_cache(user, django_assert_num_queries):
    grant(user, 'Employee', 'mock.view')
    clear_permission_cache(user)

    with django_assert_num_queries(1):
        get_user_permission_codes(user)
        get_user_permission_codes(user)
        user_has_permission(user, 'mock.view')
        user_has_permission(user, 'user.view')
        user_has_all_permissions(user, ['mock.view'])


def test_ineligible_users_cost_no_queries(django_assert_num_queries):
    with django_assert_num_queries(0):
        get_user_permission_codes(None)
        user_has_permission(None, 'mock.view')


def test_clear_permission_cache_forces_a_refetch(user, django_assert_num_queries):
    grant(user, 'Employee', 'mock.view')
    clear_permission_cache(user)
    get_user_permission_codes(user)

    clear_permission_cache(user)
    with django_assert_num_queries(1):
        get_user_permission_codes(user)


def test_cache_is_per_user_instance(user):
    grant(user, 'Employee', 'mock.view')
    get_user_permission_codes(user)

    # A freshly loaded instance must not inherit another instance's cache.
    reloaded = User.objects.get(pk=user.pk)
    grant(reloaded, 'Manager', 'user.view')

    assert get_user_permission_codes(reloaded) == {'mock.view', 'user.view'}
