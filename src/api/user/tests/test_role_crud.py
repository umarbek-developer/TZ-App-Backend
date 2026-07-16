import pytest

from apps.rbac.models import Permission, Role, RolePermission, UserRole

from .conftest import grant

URL = '/api/v1/roles/'

pytestmark = pytest.mark.django_db


def detail(role):
    return f'{URL}{role.pk}/'


@pytest.fixture
def role():
    return Role.objects.create(name='Manager', description='Runs a team')


# --- authentication: anonymous is 401 everywhere -----------------------------


def test_list_requires_authentication(api):
    assert api.get(URL).status_code == 401


def test_retrieve_requires_authentication(api, role):
    assert api.get(detail(role)).status_code == 401


def test_create_requires_authentication(api):
    assert api.post(URL, {'name': 'X'}, format='json').status_code == 401


def test_update_requires_authentication(api, role):
    assert api.put(detail(role), {'name': 'X'}, format='json').status_code == 401


def test_partial_update_requires_authentication(api, role):
    assert api.patch(detail(role), {'name': 'X'}, format='json').status_code == 401


def test_delete_requires_authentication(api, role):
    assert api.delete(detail(role)).status_code == 401


# --- authorization: wrong permission is 403 ----------------------------------


def test_employee_cannot_list(employee_client):
    assert employee_client.get(URL).status_code == 403


def test_guest_cannot_list(guest_client):
    assert guest_client.get(URL).status_code == 403


def test_employee_cannot_create(employee_client):
    assert employee_client.post(URL, {'name': 'X'}, format='json').status_code == 403


def test_viewer_can_read_but_not_create(viewer_client):
    assert viewer_client.get(URL).status_code == 200
    assert viewer_client.post(URL, {'name': 'X'}, format='json').status_code == 403


def test_viewer_cannot_update(viewer_client, role):
    assert viewer_client.patch(detail(role), {'name': 'X'}, format='json').status_code == 403


def test_viewer_cannot_delete(viewer_client, role):
    assert viewer_client.delete(detail(role)).status_code == 403
    assert Role.objects.filter(pk=role.pk).exists()


def test_read_and_write_are_gated_by_different_codes(admin_client, viewer_client):
    """role.view opens reads; writes additionally need role.manage."""
    assert viewer_client.get(URL).status_code == 200
    assert viewer_client.post(URL, {'name': 'A'}, format='json').status_code == 403
    assert admin_client.post(URL, {'name': 'A'}, format='json').status_code == 201


def test_permission_reaches_a_user_through_any_role(employee, employee_client):
    assert employee_client.get(URL).status_code == 403

    # A second role carrying role.view is enough — permissions union across roles.
    grant(employee, 'Auditor', 'role.view')

    assert employee_client.get(URL).status_code == 200


# --- read --------------------------------------------------------------------


def test_admin_can_list(admin_client, role):
    response = admin_client.get(URL)

    assert response.status_code == 200
    names = [r['name'] for r in response.data['results']]
    assert 'Manager' in names


def test_admin_can_retrieve(admin_client, role):
    response = admin_client.get(detail(role))

    assert response.status_code == 200
    assert response.data['name'] == 'Manager'
    assert response.data['description'] == 'Runs a team'


def test_retrieve_unknown_role_is_404(admin_client):
    assert admin_client.get(f'{URL}11111111-1111-1111-1111-111111111111/').status_code == 404


def test_payload_exposes_the_roles_permission_codes(admin_client, role):
    permission, _ = Permission.objects.get_or_create(code='mock.view', defaults={'name': 'View'})
    RolePermission.objects.create(role=role, permission=permission)

    response = admin_client.get(detail(role))

    assert response.data['permissions'] == ['mock.view']


def test_permissions_are_read_only(admin_client, role):
    Permission.objects.get_or_create(code='user.delete', defaults={'name': 'Delete users'})

    response = admin_client.patch(
        detail(role), {'permissions': ['user.delete']}, format='json'
    )

    assert response.status_code == 200
    # Grants are managed by the assign-permission endpoint, not by editing a role.
    assert response.data['permissions'] == []


# --- create ------------------------------------------------------------------


def test_admin_can_create(admin_client):
    response = admin_client.post(
        URL, {'name': 'Auditor', 'description': 'Reads everything'}, format='json'
    )

    assert response.status_code == 201, response.data
    assert Role.objects.filter(name='Auditor').exists()
    assert response.data['permissions'] == []


def test_create_without_description_is_allowed(admin_client):
    response = admin_client.post(URL, {'name': 'Auditor'}, format='json')

    assert response.status_code == 201
    assert Role.objects.get(name='Auditor').description == ''


def test_create_returns_a_uuid_id(admin_client):
    response = admin_client.post(URL, {'name': 'Auditor'}, format='json')

    assert str(Role.objects.get(name='Auditor').pk) == response.data['id']


# --- validation --------------------------------------------------------------


def test_create_rejects_a_duplicate_name(admin_client, role):
    response = admin_client.post(URL, {'name': 'Manager'}, format='json')

    assert response.status_code == 400
    assert 'name' in response.data['errors']
    assert Role.objects.filter(name='Manager').count() == 1


def test_create_rejects_a_duplicate_name_case_insensitively(admin_client, role):
    response = admin_client.post(URL, {'name': 'MANAGER'}, format='json')

    assert response.status_code == 400
    assert 'name' in response.data['errors']


def test_create_rejects_a_blank_name(admin_client):
    response = admin_client.post(URL, {'name': ''}, format='json')

    assert response.status_code == 400
    assert 'name' in response.data['errors']


def test_create_rejects_a_whitespace_only_name(admin_client):
    response = admin_client.post(URL, {'name': '   '}, format='json')

    assert response.status_code == 400


def test_create_rejects_a_missing_name(admin_client):
    response = admin_client.post(URL, {'description': 'no name'}, format='json')

    assert response.status_code == 400
    assert 'name' in response.data['errors']


def test_create_rejects_an_overlong_name(admin_client):
    response = admin_client.post(URL, {'name': 'x' * 101}, format='json')

    assert response.status_code == 400


def test_create_strips_surrounding_whitespace(admin_client):
    response = admin_client.post(URL, {'name': '  Auditor  '}, format='json')

    assert response.status_code == 201
    assert response.data['name'] == 'Auditor'


def test_update_may_keep_its_own_name(admin_client, role):
    """The uniqueness check must not fire against the instance being edited."""
    response = admin_client.put(
        detail(role), {'name': 'Manager', 'description': 'Changed'}, format='json'
    )

    assert response.status_code == 200, response.data
    assert response.data['description'] == 'Changed'


def test_update_rejects_a_name_taken_by_another_role(admin_client, role):
    Role.objects.create(name='Auditor')

    response = admin_client.patch(detail(role), {'name': 'Auditor'}, format='json')

    assert response.status_code == 400
    assert 'name' in response.data['errors']


def test_read_only_fields_cannot_be_written(admin_client, role):
    original_id = str(role.pk)

    response = admin_client.patch(
        detail(role),
        {'id': '99999999-9999-9999-9999-999999999999', 'name': 'Manager'},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['id'] == original_id


# --- update ------------------------------------------------------------------


def test_admin_can_replace_with_put(admin_client, role):
    response = admin_client.put(
        detail(role), {'name': 'Lead', 'description': 'Replaced'}, format='json'
    )

    assert response.status_code == 200, response.data
    role.refresh_from_db()
    assert role.name == 'Lead'
    assert role.description == 'Replaced'


def test_put_requires_the_name(admin_client, role):
    response = admin_client.put(detail(role), {'description': 'no name'}, format='json')

    assert response.status_code == 400


def test_admin_can_patch(admin_client, role):
    response = admin_client.patch(detail(role), {'description': 'Patched'}, format='json')

    assert response.status_code == 200
    role.refresh_from_db()
    assert role.description == 'Patched'
    # Untouched fields survive a partial update.
    assert role.name == 'Manager'


# --- delete ------------------------------------------------------------------


def test_admin_can_delete(admin_client, role):
    response = admin_client.delete(detail(role))

    assert response.status_code == 204
    assert not Role.objects.filter(pk=role.pk).exists()


def test_delete_removes_grants_but_not_users_or_permissions(admin_client, role, employee):
    permission = Permission.objects.create(code='mock.edit', name='Edit mock')
    RolePermission.objects.create(role=role, permission=permission)
    UserRole.objects.create(user=employee, role=role)

    admin_client.delete(detail(role))

    assert not RolePermission.objects.filter(role_id=role.pk).exists()
    assert not UserRole.objects.filter(role_id=role.pk).exists()
    assert Permission.objects.filter(pk=permission.pk).exists()
    assert employee.__class__.objects.filter(pk=employee.pk).exists()


def test_delete_unknown_role_is_404(admin_client):
    assert admin_client.delete(f'{URL}11111111-1111-1111-1111-111111111111/').status_code == 404
