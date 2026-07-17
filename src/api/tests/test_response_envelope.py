"""The response envelope, asserted against the wire format of every endpoint.

`response.data` is checked elsewhere; here everything goes through
`response.json()` so the assertions describe the bytes a client actually receives.
"""

import pytest

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.users.models import User

pytestmark = pytest.mark.django_db

SUCCESS_KEYS = {'success', 'message', 'data'}
ERROR_KEYS = {'success', 'message', 'errors'}
PASSWORD = 'Password123!'


@pytest.fixture
def admin(db):
    user = User.objects.create_user(
        email='env-admin@test.com', password=PASSWORD, first_name='A', is_active=True
    )
    role = Role.objects.create(name='EnvAdmin')
    UserRole.objects.create(user=user, role=role)
    for code in ('role.view', 'role.manage', 'permission.view', 'permission.manage', 'mock.view'):
        permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code})
        RolePermission.objects.create(role=role, permission=permission)
    return user


@pytest.fixture
def client(api, admin):
    token = api.post(
        '/api/v1/auth/login/',
        {'email': admin.email, 'password': PASSWORD},
        format='json',
    ).json()['data']['access']
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


@pytest.fixture
def api():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def role(db):
    return Role.objects.create(name='EnvTarget')


# --- success envelope --------------------------------------------------------


def test_login_is_enveloped(api, admin):
    response = api.post(
        '/api/v1/auth/login/', {'email': admin.email, 'password': PASSWORD}, format='json'
    )

    body = response.json()
    assert set(body) == SUCCESS_KEYS
    assert body['success'] is True
    assert body['message'] == 'Login successful.'
    assert set(body['data']) == {'refresh', 'access'}


def test_register_is_enveloped(api):
    response = api.post(
        '/api/v1/auth/register/',
        {
            'first_name': 'Env',
            'last_name': 'Test',
            'email': 'env-new@test.com',
            'password': PASSWORD,
            'confirm_password': PASSWORD,
        },
        format='json',
    )

    body = response.json()
    assert response.status_code == 201
    assert set(body) == SUCCESS_KEYS
    assert body['message'] == 'Registration successful.'
    assert body['data']['email'] == 'env-new@test.com'


def test_profile_is_enveloped(client):
    body = client.get('/api/v1/auth/profile/').json()

    assert set(body) == SUCCESS_KEYS
    assert body['message'] == 'Profile retrieved successfully.'
    assert body['data']['email'] == 'env-admin@test.com'


def test_list_nests_pagination_inside_data(client, role):
    body = client.get('/api/v1/roles/').json()

    assert set(body) == SUCCESS_KEYS
    assert body['message'] == 'Roles retrieved successfully.'
    assert set(body['data']) >= {'count', 'pages', 'results'}
    assert isinstance(body['data']['results'], list)


def test_detail_is_enveloped(client, role):
    body = client.get(f'/api/v1/roles/{role.pk}/').json()

    assert set(body) == SUCCESS_KEYS
    assert body['data']['name'] == 'EnvTarget'


def test_create_is_enveloped(client):
    response = client.post('/api/v1/roles/', {'name': 'EnvCreated'}, format='json')

    body = response.json()
    assert response.status_code == 201
    assert body['message'] == 'Role created successfully.'
    assert body['data']['name'] == 'EnvCreated'


def test_update_is_enveloped(client, role):
    body = client.patch(f'/api/v1/roles/{role.pk}/', {'description': 'x'}, format='json').json()

    assert set(body) == SUCCESS_KEYS
    assert body['message'] == 'Role updated successfully.'


def test_mock_arrays_are_enveloped_under_data(client):
    response = client.get('/api/v1/mock/projects/')

    body = response.json()
    assert set(body) == SUCCESS_KEYS
    assert body['message'] == 'Projects retrieved successfully.'
    # The array itself is preserved verbatim — it just travels under `data`.
    assert body['data'] == [{'id': 1, 'name': 'CRM'}, {'id': 2, 'name': 'ERP'}]


# --- the former 204/205 endpoints --------------------------------------------


def test_delete_role_answers_200_with_an_envelope(client, role):
    response = client.delete(f'/api/v1/roles/{role.pk}/')

    body = response.json()
    # 200, not 204: HTTP forbids a body on 204, and every response carries one.
    assert response.status_code == 200
    assert set(body) == SUCCESS_KEYS
    assert body['message'] == 'Role deleted successfully.'
    assert body['data'] == {}
    assert not Role.objects.filter(pk=role.pk).exists()


def test_logout_answers_200_with_an_envelope(api, admin):
    tokens = api.post(
        '/api/v1/auth/login/', {'email': admin.email, 'password': PASSWORD}, format='json'
    ).json()['data']
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    response = api.post('/api/v1/auth/logout/', {'refresh': tokens['refresh']}, format='json')

    body = response.json()
    assert response.status_code == 200
    assert body == {'success': True, 'message': 'Logged out successfully.', 'data': {}}


def test_delete_profile_answers_200_with_an_envelope(client, admin):
    response = client.delete('/api/v1/auth/profile/')

    body = response.json()
    assert response.status_code == 200
    assert body == {'success': True, 'message': 'Account deleted successfully.', 'data': {}}
    admin.refresh_from_db()
    assert admin.is_active is False


# --- error envelope ----------------------------------------------------------


def test_401_is_enveloped(api):
    body = api.get('/api/v1/roles/').json()

    assert set(body) == ERROR_KEYS
    assert body['success'] is False
    assert body['errors'] == {}


def test_403_is_enveloped(api, db):
    user = User.objects.create_user(
        email='env-nobody@test.com', password=PASSWORD, first_name='N', is_active=True
    )
    token = api.post(
        '/api/v1/auth/login/', {'email': user.email, 'password': PASSWORD}, format='json'
    ).json()['data']['access']
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    response = api.get('/api/v1/roles/')

    assert response.status_code == 403
    assert set(response.json()) == ERROR_KEYS


def test_400_is_enveloped(client):
    response = client.post('/api/v1/roles/', {'name': ''}, format='json')

    body = response.json()
    assert response.status_code == 400
    assert set(body) == ERROR_KEYS
    assert body['errors']['name']


def test_404_is_enveloped(client):
    response = client.get('/api/v1/roles/11111111-1111-1111-1111-111111111111/')

    assert response.status_code == 404
    assert set(response.json()) == ERROR_KEYS


def test_405_is_enveloped(client):
    response = client.post('/api/v1/mock/projects/', {}, format='json')

    assert response.status_code == 405
    assert set(response.json()) == ERROR_KEYS


# --- invariants --------------------------------------------------------------


@pytest.mark.parametrize(
    'method,url',
    [
        ('get', '/api/v1/roles/'),
        ('get', '/api/v1/permissions/'),
        ('get', '/api/v1/mock/projects/'),
        ('get', '/api/v1/mock/orders/'),
        ('get', '/api/v1/mock/employees/'),
        ('get', '/api/v1/mock/documents/'),
        ('get', '/api/v1/auth/profile/'),
    ],
)
def test_every_read_endpoint_uses_the_success_envelope(client, method, url):
    body = getattr(client, method)(url).json()

    assert set(body) == SUCCESS_KEYS
    assert body['success'] is True
    assert isinstance(body['message'], str) and body['message']


def test_success_and_error_envelopes_never_mix(client):
    ok = client.get('/api/v1/roles/').json()
    bad = client.post('/api/v1/roles/', {'name': ''}, format='json').json()

    assert 'errors' not in ok
    assert 'data' not in bad
    assert ok['success'] is True
    assert bad['success'] is False


def test_the_envelope_is_not_applied_twice(client):
    body = client.get('/api/v1/roles/').json()

    assert 'success' not in body['data']
    assert 'message' not in body['data']


def test_the_openapi_schema_endpoint_is_not_enveloped(client):
    """The schema is not an API resource — wrapping it would break Swagger UI."""
    response = client.get('/api/v1/schema/')

    assert response.status_code == 200
    assert b'openapi' in response.content[:200]
