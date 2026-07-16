import pytest

from apps.rbac.models import Permission, Role, RolePermission

from .conftest import grant

URL = '/api/v1/permissions/'

pytestmark = pytest.mark.django_db


def detail(permission):
    return f'{URL}{permission.pk}/'


@pytest.fixture
def permission():
    return Permission.objects.create(
        code='mock.view', name='View mock objects', description='Read the mock endpoints.'
    )


# --- authentication: anonymous is 401 everywhere -----------------------------


def test_list_requires_authentication(api):
    assert api.get(URL).status_code == 401


def test_retrieve_requires_authentication(api, permission):
    assert api.get(detail(permission)).status_code == 401


def test_create_requires_authentication(api):
    assert api.post(URL, {'code': 'x.y', 'name': 'X'}, format='json').status_code == 401


def test_update_requires_authentication(api, permission):
    response = api.put(detail(permission), {'code': 'x.y', 'name': 'X'}, format='json')

    assert response.status_code == 401


def test_partial_update_requires_authentication(api, permission):
    assert api.patch(detail(permission), {'name': 'X'}, format='json').status_code == 401


def test_delete_requires_authentication(api, permission):
    assert api.delete(detail(permission)).status_code == 401


# --- authorization: wrong permission is 403 ----------------------------------


def test_employee_cannot_list(employee_client):
    assert employee_client.get(URL).status_code == 403


def test_guest_cannot_list(guest_client):
    assert guest_client.get(URL).status_code == 403


def test_role_view_does_not_grant_permission_view(viewer_client):
    """The two resources are gated by separate codes."""
    assert viewer_client.get('/api/v1/roles/').status_code == 200
    assert viewer_client.get(URL).status_code == 403


def test_permission_view_does_not_grant_role_view(permission_viewer_client):
    assert permission_viewer_client.get(URL).status_code == 200
    assert permission_viewer_client.get('/api/v1/roles/').status_code == 403


def test_permission_viewer_can_read_but_not_create(permission_viewer_client):
    assert permission_viewer_client.get(URL).status_code == 200
    assert permission_viewer_client.post(
        URL, {'code': 'x.y', 'name': 'X'}, format='json'
    ).status_code == 403


def test_permission_viewer_cannot_update(permission_viewer_client, permission):
    assert permission_viewer_client.patch(
        detail(permission), {'name': 'X'}, format='json'
    ).status_code == 403


def test_permission_viewer_cannot_delete(permission_viewer_client, permission):
    assert permission_viewer_client.delete(detail(permission)).status_code == 403
    assert Permission.objects.filter(pk=permission.pk).exists()


def test_permission_reaches_a_user_through_any_role(employee, employee_client):
    assert employee_client.get(URL).status_code == 403

    grant(employee, 'TestAuditor', 'permission.view')

    assert employee_client.get(URL).status_code == 200


# --- read --------------------------------------------------------------------


def test_admin_can_list(admin_client, permission):
    response = admin_client.get(URL)

    assert response.status_code == 200
    assert 'mock.view' in [p['code'] for p in response.data['results']]


def test_admin_can_retrieve(admin_client, permission):
    response = admin_client.get(detail(permission))

    assert response.status_code == 200
    assert response.data['code'] == 'mock.view'
    assert response.data['name'] == 'View mock objects'


def test_retrieve_unknown_permission_is_404(admin_client):
    assert admin_client.get(f'{URL}11111111-1111-1111-1111-111111111111/').status_code == 404


def test_payload_exposes_the_roles_holding_the_permission(admin_client, permission):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=permission)

    response = admin_client.get(detail(permission))

    assert response.data['roles'] == ['Manager']


def test_roles_are_read_only(admin_client, permission):
    Role.objects.create(name='Manager')

    response = admin_client.patch(detail(permission), {'roles': ['Manager']}, format='json')

    assert response.status_code == 200
    # Grants are managed by the assign-permission endpoint.
    assert response.data['roles'] == []


# --- create ------------------------------------------------------------------


def test_admin_can_create(admin_client):
    response = admin_client.post(
        URL, {'code': 'report.export', 'name': 'Export reports'}, format='json'
    )

    assert response.status_code == 201, response.data
    assert Permission.objects.filter(code='report.export').exists()
    assert response.data['roles'] == []


def test_create_without_description_is_allowed(admin_client):
    response = admin_client.post(URL, {'code': 'report.export', 'name': 'X'}, format='json')

    assert response.status_code == 201
    assert Permission.objects.get(code='report.export').description == ''


# --- validation --------------------------------------------------------------


def test_create_rejects_a_duplicate_code(admin_client, permission):
    response = admin_client.post(URL, {'code': 'mock.view', 'name': 'Dup'}, format='json')

    assert response.status_code == 400
    assert 'code' in response.data
    assert Permission.objects.filter(code='mock.view').count() == 1


def test_create_rejects_a_duplicate_code_case_insensitively(admin_client, permission):
    response = admin_client.post(URL, {'code': 'MOCK.VIEW', 'name': 'Dup'}, format='json')

    assert response.status_code == 400
    assert 'code' in response.data


def test_create_lowercases_the_code(admin_client):
    """Checks match codes by exact string, so a stored "Mock.Edit" could never fire."""
    response = admin_client.post(URL, {'code': 'Mock.Edit', 'name': 'Edit'}, format='json')

    assert response.status_code == 201, response.data
    assert response.data['code'] == 'mock.edit'


def test_create_strips_surrounding_whitespace(admin_client):
    response = admin_client.post(URL, {'code': '  mock.edit  ', 'name': '  Edit  '}, format='json')

    assert response.status_code == 201
    assert response.data['code'] == 'mock.edit'
    assert response.data['name'] == 'Edit'


@pytest.mark.parametrize(
    'bad_code',
    [
        'mock view',   # space
        'mock..view',  # empty segment
        '.mock.view',  # leading dot
        'mock.view.',  # trailing dot
        'mock/view',   # bad separator
        'mock!view',   # punctuation
        '',            # blank
    ],
)
def test_create_rejects_a_malformed_code(admin_client, bad_code):
    response = admin_client.post(URL, {'code': bad_code, 'name': 'X'}, format='json')

    assert response.status_code == 400, f'{bad_code!r} should be rejected'
    assert 'code' in response.data


@pytest.mark.parametrize('good_code', ['mock.view', 'a.b.c', 'user_role.view', 'report-x.export'])
def test_create_accepts_conventional_codes(admin_client, good_code):
    response = admin_client.post(URL, {'code': good_code, 'name': 'X'}, format='json')

    assert response.status_code == 201, response.data


def test_create_rejects_a_missing_code(admin_client):
    response = admin_client.post(URL, {'name': 'X'}, format='json')

    assert response.status_code == 400
    assert 'code' in response.data


def test_create_rejects_a_missing_name(admin_client):
    response = admin_client.post(URL, {'code': 'mock.edit'}, format='json')

    assert response.status_code == 400
    assert 'name' in response.data


def test_create_rejects_an_overlong_code(admin_client):
    response = admin_client.post(URL, {'code': 'x' * 101, 'name': 'X'}, format='json')

    assert response.status_code == 400


def test_update_may_keep_its_own_code(admin_client, permission):
    """The uniqueness check must not fire against the instance being edited."""
    response = admin_client.put(
        detail(permission), {'code': 'mock.view', 'name': 'Renamed'}, format='json'
    )

    assert response.status_code == 200, response.data
    assert response.data['name'] == 'Renamed'


def test_update_rejects_a_code_taken_by_another_permission(admin_client, permission):
    Permission.objects.create(code='user.view', name='View users')

    response = admin_client.patch(detail(permission), {'code': 'user.view'}, format='json')

    assert response.status_code == 400
    assert 'code' in response.data


def test_read_only_fields_cannot_be_written(admin_client, permission):
    original_id = str(permission.pk)

    response = admin_client.patch(
        detail(permission),
        {'id': '99999999-9999-9999-9999-999999999999', 'name': 'X'},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['id'] == original_id


# --- update ------------------------------------------------------------------


def test_admin_can_replace_with_put(admin_client, permission):
    response = admin_client.put(
        detail(permission), {'code': 'mock.read', 'name': 'Read mock'}, format='json'
    )

    assert response.status_code == 200, response.data
    permission.refresh_from_db()
    assert permission.code == 'mock.read'
    assert permission.name == 'Read mock'


def test_put_requires_the_code(admin_client, permission):
    response = admin_client.put(detail(permission), {'name': 'X'}, format='json')

    assert response.status_code == 400


def test_admin_can_patch(admin_client, permission):
    response = admin_client.patch(detail(permission), {'name': 'Patched'}, format='json')

    assert response.status_code == 200
    permission.refresh_from_db()
    assert permission.name == 'Patched'
    assert permission.code == 'mock.view'


def test_renaming_a_code_moves_the_grant(admin_client, permission):
    """A role keeps the row, so its granted code follows the rename."""
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=permission)

    admin_client.patch(detail(permission), {'code': 'mock.read'}, format='json')

    assert list(role.permissions.values_list('code', flat=True)) == ['mock.read']


# --- delete ------------------------------------------------------------------


def test_admin_can_delete(admin_client, permission):
    response = admin_client.delete(detail(permission))

    assert response.status_code == 204
    assert not Permission.objects.filter(pk=permission.pk).exists()


def test_delete_removes_grants_but_not_roles(admin_client, permission):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=permission)

    admin_client.delete(detail(permission))

    assert not RolePermission.objects.filter(permission_id=permission.pk).exists()
    assert Role.objects.filter(pk=role.pk).exists()


def test_delete_unknown_permission_is_404(admin_client):
    assert admin_client.delete(f'{URL}11111111-1111-1111-1111-111111111111/').status_code == 404
