import pytest

from apps.rbac.models import Role, UserRole
from apps.rbac.services import get_user_permission_codes

from .conftest import grant, make_user

URL = '/api/v1/assign-role/'

pytestmark = pytest.mark.django_db


@pytest.fixture
def target():
    """A plain user with no roles."""
    return make_user('target@test.com')


@pytest.fixture
def roles():
    return {
        name: Role.objects.create(name=name) for name in ('Manager', 'Employee', 'Guest')
    }


def body(user, *roles):
    return {'user': str(user.pk), 'roles': [str(r.pk) for r in roles]}


def held(user):
    return sorted(UserRole.objects.filter(user=user).values_list('role__name', flat=True))


# --- authentication / authorization ------------------------------------------


def test_assign_requires_authentication(api, target, roles):
    assert api.post(URL, body(target, roles['Manager']), format='json').status_code == 401


def test_replace_requires_authentication(api, target, roles):
    assert api.put(URL, body(target, roles['Manager']), format='json').status_code == 401


def test_remove_requires_authentication(api, target, roles):
    assert api.delete(URL, body(target, roles['Manager']), format='json').status_code == 401


def test_employee_cannot_assign(employee_client, target, roles):
    response = employee_client.post(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 403
    assert not UserRole.objects.filter(user=target).exists()


def test_role_viewer_cannot_assign(viewer_client, target, roles):
    """role.view opens reads; assignment needs role.manage."""
    assert viewer_client.get('/api/v1/roles/').status_code == 200
    assert viewer_client.post(URL, body(target, roles['Manager']), format='json').status_code == 403


def test_permission_manager_cannot_assign_roles(permission_viewer_client, target, roles):
    response = permission_viewer_client.post(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 403


# --- assign (POST) -----------------------------------------------------------


def test_assign_a_single_role(admin_client, target, roles):
    response = admin_client.post(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 200, response.data
    assert held(target) == ['Manager']


def test_assign_several_roles(admin_client, target, roles):
    response = admin_client.post(
        URL, body(target, roles['Manager'], roles['Employee']), format='json'
    )

    assert response.status_code == 200
    assert held(target) == ['Employee', 'Manager']


def test_assign_keeps_existing_roles(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Guest'])

    admin_client.post(URL, body(target, roles['Manager']), format='json')

    assert held(target) == ['Guest', 'Manager']


def test_assign_response_shape(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Guest'])

    response = admin_client.post(
        URL, body(target, roles['Manager'], roles['Guest']), format='json'
    )

    assert response.data == {
        'user': {
            'id': str(target.pk),
            'email': 'target@test.com',
            'full_name': target.full_name,
            'is_active': True,
        },
        'roles': ['Guest', 'Manager'],
        'added': ['Manager'],
        'already_assigned': ['Guest'],
    }


def test_assigning_an_already_held_role_is_a_noop(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])

    response = admin_client.post(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 200
    assert response.data['added'] == []
    assert response.data['already_assigned'] == ['Manager']
    # No duplicate row.
    assert UserRole.objects.filter(user=target, role=roles['Manager']).count() == 1


def test_assign_is_idempotent(admin_client, target, roles):
    for _ in range(3):
        admin_client.post(URL, body(target, roles['Manager']), format='json')

    assert UserRole.objects.filter(user=target).count() == 1


def test_assign_grants_the_roles_permissions(admin_client, target):
    grant(make_user('other@test.com'), 'Auditor', 'mock.view')
    auditor = Role.objects.get(name='Auditor')

    admin_client.post(URL, body(target, auditor), format='json')

    assert get_user_permission_codes(target) == {'mock.view'}


# --- validation --------------------------------------------------------------


def test_unknown_user_is_400(admin_client, roles):
    response = admin_client.post(
        URL,
        {'user': '11111111-1111-1111-1111-111111111111', 'roles': [str(roles['Manager'].pk)]},
        format='json',
    )

    assert response.status_code == 400
    assert 'user' in response.data


def test_unknown_role_is_400(admin_client, target):
    response = admin_client.post(
        URL,
        {'user': str(target.pk), 'roles': ['11111111-1111-1111-1111-111111111111']},
        format='json',
    )

    assert response.status_code == 400
    assert 'roles' in response.data


def test_one_unknown_role_rejects_the_whole_request(admin_client, target, roles):
    response = admin_client.post(
        URL,
        {
            'user': str(target.pk),
            'roles': [str(roles['Manager'].pk), '11111111-1111-1111-1111-111111111111'],
        },
        format='json',
    )

    assert response.status_code == 400
    # Atomic: the valid half must not land either.
    assert not UserRole.objects.filter(user=target).exists()


def test_duplicate_role_ids_are_400(admin_client, target, roles):
    response = admin_client.post(
        URL,
        {'user': str(target.pk), 'roles': [str(roles['Manager'].pk)] * 2},
        format='json',
    )

    assert response.status_code == 400
    assert 'roles' in response.data


def test_missing_user_is_400(admin_client, roles):
    response = admin_client.post(URL, {'roles': [str(roles['Manager'].pk)]}, format='json')

    assert response.status_code == 400
    assert 'user' in response.data


def test_missing_roles_is_400(admin_client, target):
    response = admin_client.post(URL, {'user': str(target.pk)}, format='json')

    assert response.status_code == 400
    assert 'roles' in response.data


def test_empty_role_list_is_400_on_assign(admin_client, target):
    response = admin_client.post(URL, {'user': str(target.pk), 'roles': []}, format='json')

    assert response.status_code == 400
    assert 'roles' in response.data


def test_malformed_uuid_is_400(admin_client, roles):
    response = admin_client.post(
        URL, {'user': 'not-a-uuid', 'roles': [str(roles['Manager'].pk)]}, format='json'
    )

    assert response.status_code == 400


def test_inactive_user_can_still_be_assigned(admin_client, roles):
    """Assignment is bookkeeping; an inactive user simply resolves no permissions."""
    inactive = make_user('inactive@test.com', is_active=False)

    response = admin_client.post(URL, body(inactive, roles['Manager']), format='json')

    assert response.status_code == 200
    assert response.data['user']['is_active'] is False
    assert held(inactive) == ['Manager']


# --- replace (PUT) -----------------------------------------------------------


def test_replace_sets_exactly_the_given_roles(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Guest'])

    response = admin_client.put(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 200, response.data
    assert held(target) == ['Manager']


def test_replace_response_shape(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Guest'])
    UserRole.objects.create(user=target, role=roles['Employee'])

    response = admin_client.put(
        URL, body(target, roles['Manager'], roles['Employee']), format='json'
    )

    assert response.data['roles'] == ['Employee', 'Manager']
    assert response.data['added'] == ['Manager']
    assert response.data['removed'] == ['Guest']
    assert response.data['unchanged'] == ['Employee']


def test_replace_with_an_empty_list_strips_every_role(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Guest'])
    UserRole.objects.create(user=target, role=roles['Manager'])

    response = admin_client.put(URL, {'user': str(target.pk), 'roles': []}, format='json')

    assert response.status_code == 200
    assert held(target) == []
    assert response.data['removed'] == ['Guest', 'Manager']


def test_replace_is_idempotent(admin_client, target, roles):
    for _ in range(3):
        response = admin_client.put(URL, body(target, roles['Manager']), format='json')

    assert UserRole.objects.filter(user=target).count() == 1
    assert response.data['added'] == []
    assert response.data['unchanged'] == ['Manager']


def test_replace_revokes_the_old_roles_permissions(admin_client, target):
    grant(make_user('a@test.com'), 'Auditor', 'mock.view')
    grant(make_user('b@test.com'), 'Clerk', 'user.view')
    UserRole.objects.create(user=target, role=Role.objects.get(name='Auditor'))

    admin_client.put(URL, body(target, Role.objects.get(name='Clerk')), format='json')

    assert get_user_permission_codes(target) == {'user.view'}


def test_replace_rejects_an_unknown_role(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Guest'])

    response = admin_client.put(
        URL,
        {'user': str(target.pk), 'roles': ['11111111-1111-1111-1111-111111111111']},
        format='json',
    )

    assert response.status_code == 400
    # The existing role must survive a rejected replacement.
    assert held(target) == ['Guest']


# --- remove (DELETE) ---------------------------------------------------------


def test_remove_revokes_the_role(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])

    response = admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 200, response.data
    assert held(target) == []


def test_remove_leaves_other_roles(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])
    UserRole.objects.create(user=target, role=roles['Guest'])

    admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert held(target) == ['Guest']


def test_remove_response_shape(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])

    response = admin_client.delete(
        URL, body(target, roles['Manager'], roles['Guest']), format='json'
    )

    assert response.data['roles'] == []
    assert response.data['removed'] == ['Manager']
    assert response.data['not_assigned'] == ['Guest']


def test_removing_a_role_the_user_lacks_is_a_noop(admin_client, target, roles):
    response = admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert response.status_code == 200
    assert response.data['removed'] == []
    assert response.data['not_assigned'] == ['Manager']


def test_remove_is_idempotent(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])

    for _ in range(3):
        admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert held(target) == []


def test_remove_revokes_the_permissions(admin_client, target):
    grant(make_user('a@test.com'), 'Auditor', 'mock.view')
    auditor = Role.objects.get(name='Auditor')
    UserRole.objects.create(user=target, role=auditor)

    admin_client.delete(URL, body(target, auditor), format='json')

    assert get_user_permission_codes(target) == frozenset()


def test_remove_does_not_delete_the_role_itself(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])

    admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert Role.objects.filter(name='Manager').exists()


def test_remove_does_not_delete_the_user(admin_client, target, roles):
    UserRole.objects.create(user=target, role=roles['Manager'])

    admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert target.__class__.objects.filter(pk=target.pk).exists()


def test_remove_does_not_touch_other_users(admin_client, target, roles):
    other = make_user('other@test.com')
    UserRole.objects.create(user=target, role=roles['Manager'])
    UserRole.objects.create(user=other, role=roles['Manager'])

    admin_client.delete(URL, body(target, roles['Manager']), format='json')

    assert held(other) == ['Manager']
