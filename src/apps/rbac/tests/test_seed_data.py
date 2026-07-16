from io import StringIO

import pytest
from django.core.management import call_command

from apps.rbac.models import Permission, Role, RolePermission

pytestmark = pytest.mark.django_db

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
    counts = (Role.objects.count(), Permission.objects.count(), RolePermission.objects.count())

    seed()

    assert (
        Role.objects.count(),
        Permission.objects.count(),
        RolePermission.objects.count(),
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
