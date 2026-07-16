import pytest

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.services import get_user_permission_codes

from .conftest import jwt_client_for, make_user

URL = '/api/v1/assign-permission/'

pytestmark = pytest.mark.django_db


@pytest.fixture
def role():
    """A role carrying nothing."""
    return Role.objects.create(name='Crew')


@pytest.fixture
def permissions():
    return {
        code: Permission.objects.get_or_create(code=code, defaults={'name': code})[0]
        for code in ('mock.view', 'user.view', 'user.update')
    }


def body(role, *permissions):
    return {'role': str(role.pk), 'permissions': [str(p.pk) for p in permissions]}


def carried(role):
    return sorted(
        RolePermission.objects.filter(role=role).values_list('permission__code', flat=True)
    )


# --- authentication / authorization ------------------------------------------


def test_assign_requires_authentication(api, role, permissions):
    assert api.post(URL, body(role, permissions['mock.view']), format='json').status_code == 401


def test_replace_requires_authentication(api, role, permissions):
    assert api.put(URL, body(role, permissions['mock.view']), format='json').status_code == 401


def test_remove_requires_authentication(api, role, permissions):
    assert api.delete(URL, body(role, permissions['mock.view']), format='json').status_code == 401


def test_employee_cannot_assign(employee_client, role, permissions):
    response = employee_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 403
    assert carried(role) == []


def test_permission_viewer_cannot_assign(permission_viewer_client, role, permissions):
    """permission.view opens reads; granting needs permission.manage."""
    assert permission_viewer_client.get('/api/v1/permissions/').status_code == 200
    assert permission_viewer_client.post(
        URL, body(role, permissions['mock.view']), format='json'
    ).status_code == 403


def test_role_manager_cannot_assign_permissions(viewer_client, role, permissions):
    """role.* codes do not open the permission-assignment endpoint."""
    response = viewer_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 403


# --- assign (POST) -----------------------------------------------------------


def test_assign_a_single_permission(admin_client, role, permissions):
    response = admin_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 200, response.data
    assert carried(role) == ['mock.view']


def test_assign_several_permissions(admin_client, role, permissions):
    response = admin_client.post(
        URL, body(role, permissions['mock.view'], permissions['user.view']), format='json'
    )

    assert response.status_code == 200
    assert carried(role) == ['mock.view', 'user.view']


def test_assign_keeps_existing_permissions(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['user.view'])

    admin_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert carried(role) == ['mock.view', 'user.view']


def test_assign_response_shape(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['user.view'])

    response = admin_client.post(
        URL, body(role, permissions['mock.view'], permissions['user.view']), format='json'
    )

    assert response.data == {
        'role': {'id': str(role.pk), 'name': 'Crew'},
        'permissions': ['mock.view', 'user.view'],
        'added': ['mock.view'],
        'already_assigned': ['user.view'],
    }


def test_assigning_an_already_carried_permission_is_a_noop(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])

    response = admin_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 200
    assert response.data['added'] == []
    assert response.data['already_assigned'] == ['mock.view']
    grants = RolePermission.objects.filter(role=role, permission=permissions['mock.view'])
    assert grants.count() == 1


def test_assign_is_idempotent(admin_client, role, permissions):
    for _ in range(3):
        admin_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert RolePermission.objects.filter(role=role).count() == 1


# --- validation --------------------------------------------------------------


def test_unknown_role_is_400(admin_client, permissions):
    response = admin_client.post(
        URL,
        {
            'role': '11111111-1111-1111-1111-111111111111',
            'permissions': [str(permissions['mock.view'].pk)],
        },
        format='json',
    )

    assert response.status_code == 400
    assert 'role' in response.data['errors']


def test_unknown_permission_is_400(admin_client, role):
    response = admin_client.post(
        URL,
        {'role': str(role.pk), 'permissions': ['11111111-1111-1111-1111-111111111111']},
        format='json',
    )

    assert response.status_code == 400
    assert 'permissions' in response.data['errors']


def test_one_unknown_permission_rejects_the_whole_request(admin_client, role, permissions):
    response = admin_client.post(
        URL,
        {
            'role': str(role.pk),
            'permissions': [
                str(permissions['mock.view'].pk),
                '11111111-1111-1111-1111-111111111111',
            ],
        },
        format='json',
    )

    assert response.status_code == 400
    # Atomic: the valid half must not land either.
    assert carried(role) == []


def test_duplicate_permission_ids_are_400(admin_client, role, permissions):
    response = admin_client.post(
        URL,
        {'role': str(role.pk), 'permissions': [str(permissions['mock.view'].pk)] * 2},
        format='json',
    )

    assert response.status_code == 400
    assert 'permissions' in response.data['errors']


def test_missing_role_is_400(admin_client, permissions):
    response = admin_client.post(
        URL, {'permissions': [str(permissions['mock.view'].pk)]}, format='json'
    )

    assert response.status_code == 400
    assert 'role' in response.data['errors']


def test_missing_permissions_is_400(admin_client, role):
    response = admin_client.post(URL, {'role': str(role.pk)}, format='json')

    assert response.status_code == 400
    assert 'permissions' in response.data['errors']


def test_empty_permission_list_is_400_on_assign(admin_client, role):
    response = admin_client.post(URL, {'role': str(role.pk), 'permissions': []}, format='json')

    assert response.status_code == 400
    assert 'permissions' in response.data['errors']


def test_malformed_uuid_is_400(admin_client, permissions):
    response = admin_client.post(
        URL,
        {'role': 'not-a-uuid', 'permissions': [str(permissions['mock.view'].pk)]},
        format='json',
    )

    assert response.status_code == 400


# --- replace (PUT) -----------------------------------------------------------


def test_replace_sets_exactly_the_given_permissions(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['user.view'])

    response = admin_client.put(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 200, response.data
    assert carried(role) == ['mock.view']


def test_replace_response_shape(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['user.view'])
    RolePermission.objects.create(role=role, permission=permissions['user.update'])

    response = admin_client.put(
        URL, body(role, permissions['mock.view'], permissions['user.update']), format='json'
    )

    assert response.data['permissions'] == ['mock.view', 'user.update']
    assert response.data['added'] == ['mock.view']
    assert response.data['removed'] == ['user.view']
    assert response.data['unchanged'] == ['user.update']


def test_replace_with_an_empty_list_strips_everything(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['user.view'])
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])

    response = admin_client.put(URL, {'role': str(role.pk), 'permissions': []}, format='json')

    assert response.status_code == 200
    assert carried(role) == []
    assert response.data['removed'] == ['mock.view', 'user.view']


def test_replace_is_idempotent(admin_client, role, permissions):
    for _ in range(3):
        response = admin_client.put(URL, body(role, permissions['mock.view']), format='json')

    assert RolePermission.objects.filter(role=role).count() == 1
    assert response.data['added'] == []
    assert response.data['unchanged'] == ['mock.view']


def test_replace_rejects_an_unknown_permission(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['user.view'])

    response = admin_client.put(
        URL,
        {'role': str(role.pk), 'permissions': ['11111111-1111-1111-1111-111111111111']},
        format='json',
    )

    assert response.status_code == 400
    # The existing grant must survive a rejected replacement.
    assert carried(role) == ['user.view']


def test_replace_does_not_touch_other_roles(admin_client, role, permissions):
    other = Role.objects.create(name='Other')
    RolePermission.objects.create(role=other, permission=permissions['user.view'])

    admin_client.put(URL, body(role, permissions['mock.view']), format='json')

    assert carried(other) == ['user.view']


# --- remove (DELETE) ---------------------------------------------------------


def test_remove_revokes_the_permission(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])

    response = admin_client.delete(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 200, response.data
    assert carried(role) == []


def test_remove_leaves_other_permissions(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])
    RolePermission.objects.create(role=role, permission=permissions['user.view'])

    admin_client.delete(URL, body(role, permissions['mock.view']), format='json')

    assert carried(role) == ['user.view']


def test_remove_response_shape(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])

    response = admin_client.delete(
        URL, body(role, permissions['mock.view'], permissions['user.view']), format='json'
    )

    assert response.data['permissions'] == []
    assert response.data['removed'] == ['mock.view']
    assert response.data['not_assigned'] == ['user.view']


def test_removing_a_permission_the_role_lacks_is_a_noop(admin_client, role, permissions):
    response = admin_client.delete(URL, body(role, permissions['mock.view']), format='json')

    assert response.status_code == 200
    assert response.data['removed'] == []
    assert response.data['not_assigned'] == ['mock.view']


def test_remove_does_not_delete_the_permission_itself(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])

    admin_client.delete(URL, body(role, permissions['mock.view']), format='json')

    assert Permission.objects.filter(code='mock.view').exists()


def test_remove_does_not_delete_the_role(admin_client, role, permissions):
    RolePermission.objects.create(role=role, permission=permissions['mock.view'])

    admin_client.delete(URL, body(role, permissions['mock.view']), format='json')

    assert Role.objects.filter(pk=role.pk).exists()


# --- the change reaches users immediately ------------------------------------
#
# These use real JWTs rather than force_authenticate, so every request re-loads
# the user exactly as production does. force_authenticate would pin one user
# object and its memoised codes, hiding the very thing under test.


def test_granting_a_permission_reaches_a_holder_on_the_very_next_request(admin_client, role):
    """No re-login, no token refresh — the next request already sees it."""
    member = make_user('member@test.com')
    UserRole.objects.create(user=member, role=role)
    member_client = jwt_client_for(member)

    assert member_client.get('/api/v1/roles/').status_code == 403

    role_view, _ = Permission.objects.get_or_create(
        code='role.view', defaults={'name': 'View roles'}
    )
    admin_client.post(URL, body(role, role_view), format='json')

    assert member_client.get('/api/v1/roles/').status_code == 200


def test_revoking_a_permission_locks_a_holder_out_on_the_very_next_request(admin_client, role):
    member = make_user('member@test.com')
    UserRole.objects.create(user=member, role=role)
    role_view, _ = Permission.objects.get_or_create(
        code='role.view', defaults={'name': 'View roles'}
    )
    RolePermission.objects.create(role=role, permission=role_view)
    member_client = jwt_client_for(member)

    assert member_client.get('/api/v1/roles/').status_code == 200

    admin_client.delete(URL, body(role, role_view), format='json')

    assert member_client.get('/api/v1/roles/').status_code == 403


def test_replacing_permissions_reaches_a_holder_immediately(admin_client, role, permissions):
    member = make_user('member@test.com')
    UserRole.objects.create(user=member, role=role)
    role_view, _ = Permission.objects.get_or_create(
        code='role.view', defaults={'name': 'View roles'}
    )
    RolePermission.objects.create(role=role, permission=role_view)
    member_client = jwt_client_for(member)

    assert member_client.get('/api/v1/roles/').status_code == 200

    # Replace role.view with something unrelated.
    admin_client.put(URL, body(role, permissions['mock.view']), format='json')

    assert member_client.get('/api/v1/roles/').status_code == 403


def test_the_grant_reaches_every_holder_of_the_role(admin_client, role):
    one = make_user('one@test.com')
    two = make_user('two@test.com')
    for member in (one, two):
        UserRole.objects.create(user=member, role=role)

    role_view, _ = Permission.objects.get_or_create(
        code='role.view', defaults={'name': 'View roles'}
    )
    admin_client.post(URL, body(role, role_view), format='json')

    assert jwt_client_for(one).get('/api/v1/roles/').status_code == 200
    assert jwt_client_for(two).get('/api/v1/roles/').status_code == 200


def test_resolved_codes_follow_the_grant(admin_client, role, permissions):
    member = make_user('member@test.com')
    UserRole.objects.create(user=member, role=role)

    admin_client.post(URL, body(role, permissions['mock.view']), format='json')

    assert get_user_permission_codes(member) == {'mock.view'}


def test_an_admin_editing_their_own_role_sees_it_immediately(admin, admin_client, permissions):
    """The caller is the one live user object in the process; its cache must drop."""
    own_role = Role.objects.get(name='TestAdmin')

    admin_client.post(URL, body(own_role, permissions['user.update']), format='json')

    assert 'user.update' in get_user_permission_codes(admin)
