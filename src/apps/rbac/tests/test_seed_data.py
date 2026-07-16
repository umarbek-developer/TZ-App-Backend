from io import StringIO

import pytest
from django.core.management import call_command

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import get_user_permission_codes
from apps.users.models import User

pytestmark = pytest.mark.django_db

ADMIN_EMAIL = 'admin@gmail.com'
ADMIN_PASSWORD = 'admin123'

EXPECTED_CODES = {
    'user.view',
    'user.update',
    'user.delete',
    'role.view',
    'role.manage',
    'permission.view',
    'permission.manage',
    'mock.view',
}

EXPECTED_GRANTS = {
    'Admin': EXPECTED_CODES,
    'Manager': {'mock.view', 'user.view'},
    'Employee': {'mock.view'},
    'Guest': set(),
}


def seed(**kwargs):
    out = StringIO()
    call_command('seed_data', stdout=out, **kwargs)
    return out.getvalue()


def codes_for(role_name):
    return set(
        RolePermission.objects.filter(role__name=role_name).values_list(
            'permission__code', flat=True
        )
    )


# --- creation ----------------------------------------------------------------


def test_seed_creates_the_four_roles():
    seed()

    assert set(Role.objects.values_list('name', flat=True)) == {
        'Admin',
        'Manager',
        'Employee',
        'Guest',
    }


def test_seed_creates_the_eight_permissions():
    seed()

    assert set(Permission.objects.values_list('code', flat=True)) == EXPECTED_CODES
    assert Permission.objects.count() == 8


def test_permissions_get_names_and_descriptions():
    seed()

    permission = Permission.objects.get(code='mock.view')
    assert permission.name
    assert permission.description


@pytest.mark.parametrize('role_name,expected', EXPECTED_GRANTS.items())
def test_role_receives_exactly_its_permissions(role_name, expected):
    seed()

    assert codes_for(role_name) == expected


def test_admin_receives_every_permission():
    seed()

    assert codes_for('Admin') == set(Permission.objects.values_list('code', flat=True))


def test_guest_receives_nothing():
    seed()

    assert codes_for('Guest') == set()


# --- idempotency -------------------------------------------------------------


def test_running_twice_creates_no_duplicates():
    seed()
    counts = (
        Role.objects.count(),
        Permission.objects.count(),
        RolePermission.objects.count(),
        User.objects.count(),
        UserRole.objects.count(),
    )

    seed()

    assert (
        Role.objects.count(),
        Permission.objects.count(),
        RolePermission.objects.count(),
        User.objects.count(),
        UserRole.objects.count(),
    ) == counts


def test_running_three_times_is_stable():
    seed()
    seed()
    seed()

    assert Role.objects.count() == 4
    assert Permission.objects.count() == 8
    assert RolePermission.objects.count() == 8 + 2 + 1 + 0  # Admin + Manager + Employee + Guest


def test_second_run_preserves_primary_keys():
    seed()
    before = dict(Role.objects.values_list('name', 'id'))

    seed()

    assert dict(Role.objects.values_list('name', 'id')) == before


def test_second_run_reports_rows_as_existing():
    seed()

    output = seed()

    assert 'created' not in output
    assert 'exists' in output


def test_seed_repairs_a_missing_grant():
    seed()
    RolePermission.objects.filter(role__name='Employee', permission__code='mock.view').delete()

    seed()

    assert codes_for('Employee') == {'mock.view'}


def test_seed_restores_an_edited_description():
    seed()
    Role.objects.filter(name='Guest').update(description='tampered')

    seed()

    assert Role.objects.get(name='Guest').description == 'Holds no permissions.'


def test_seed_coexists_with_preexisting_roles():
    Role.objects.create(name='Admin', description='made by hand')

    seed()

    assert Role.objects.filter(name='Admin').count() == 1
    assert codes_for('Admin') == EXPECTED_CODES


# --- administrator -----------------------------------------------------------


def test_seed_creates_the_administrator():
    seed()

    admin = User.objects.get(email=ADMIN_EMAIL)
    assert admin.is_superuser is True
    assert admin.is_staff is True
    assert admin.is_active is True


def test_administrator_can_authenticate_with_the_documented_password():
    seed()

    assert User.objects.get(email=ADMIN_EMAIL).check_password(ADMIN_PASSWORD)


def test_administrator_holds_the_admin_role():
    seed()

    admin = User.objects.get(email=ADMIN_EMAIL)
    assert UserRole.objects.filter(user=admin, role__name='Admin').exists()


def test_administrator_resolves_every_permission():
    """The point of the account: power comes from the role, not from is_superuser."""
    seed()

    admin = User.objects.get(email=ADMIN_EMAIL)
    assert get_user_permission_codes(admin) == EXPECTED_CODES


def test_seeding_twice_does_not_duplicate_the_administrator():
    seed()
    seed()

    assert User.objects.filter(email=ADMIN_EMAIL).count() == 1
    assert UserRole.objects.filter(user__email=ADMIN_EMAIL).count() == 1


def test_seed_does_not_reset_an_existing_administrator_password():
    seed()
    admin = User.objects.get(email=ADMIN_EMAIL)
    admin.set_password('SomethingElse123!')
    admin.save()

    seed()

    admin.refresh_from_db()
    # Re-seeding must not silently undo a deliberately changed credential.
    assert admin.check_password('SomethingElse123!')
    assert not admin.check_password(ADMIN_PASSWORD)


def test_seed_grants_the_admin_role_to_a_preexisting_administrator():
    User.objects.create_superuser(email=ADMIN_EMAIL, password=ADMIN_PASSWORD, first_name='A')

    seed()

    admin = User.objects.get(email=ADMIN_EMAIL)
    assert get_user_permission_codes(admin) == EXPECTED_CODES
    assert User.objects.filter(email=ADMIN_EMAIL).count() == 1


def test_seed_reactivates_a_soft_deleted_administrator():
    seed()
    User.objects.filter(email=ADMIN_EMAIL).update(is_active=False, is_staff=False)

    seed()

    admin = User.objects.get(email=ADMIN_EMAIL)
    assert admin.is_active is True
    assert admin.is_staff is True


def test_seed_does_not_create_other_users():
    seed()

    assert User.objects.count() == 1


# --- pruning -----------------------------------------------------------------


def test_extra_grants_survive_by_default():
    seed()
    extra = Permission.objects.get(code='user.delete')
    RolePermission.objects.create(role=Role.objects.get(name='Guest'), permission=extra)

    seed()

    # Default is additive: a grant made by hand is not silently revoked.
    assert 'user.delete' in codes_for('Guest')


def test_prune_revokes_undeclared_grants():
    seed()
    extra = Permission.objects.get(code='user.delete')
    RolePermission.objects.create(role=Role.objects.get(name='Guest'), permission=extra)

    seed(prune=True)

    assert codes_for('Guest') == set()


def test_prune_keeps_declared_grants():
    seed()

    seed(prune=True)

    assert codes_for('Manager') == {'mock.view', 'user.view'}
    assert codes_for('Admin') == EXPECTED_CODES
