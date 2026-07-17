import pytest

from .conftest import PASSWORD

URL = '/api/v1/auth/login/'

pytestmark = pytest.mark.django_db


def test_login_returns_token_pair(api, user):
    response = api.post(URL, {'email': user.email, 'password': PASSWORD}, format='json')

    assert response.status_code == 200, response.data
    assert set(response.data['data']) == {'refresh', 'access'}
    assert response.data['data']['access']
    assert response.data['data']['refresh']


def test_login_is_case_insensitive_on_email(api, user):
    response = api.post(URL, {'email': 'JOHN@GMAIL.COM', 'password': PASSWORD}, format='json')

    assert response.status_code == 200


def test_login_with_wrong_password_is_401(api, user):
    response = api.post(URL, {'email': user.email, 'password': 'WrongPass123!'}, format='json')

    assert response.status_code == 401


def test_login_with_unknown_email_is_401(api, db):
    response = api.post(URL, {'email': 'nobody@gmail.com', 'password': PASSWORD}, format='json')

    assert response.status_code == 401


def test_login_rejects_inactive_user(api, inactive_user):
    response = api.post(URL, {'email': inactive_user.email, 'password': PASSWORD}, format='json')

    assert response.status_code == 401


def test_login_requires_both_fields(api, db):
    response = api.post(URL, {'email': 'john@gmail.com'}, format='json')

    assert response.status_code == 400
    assert 'password' in response.data['errors']


def test_access_token_authenticates_a_request(api, user):
    tokens = api.post(URL, {'email': user.email, 'password': PASSWORD}, format='json').data['data']

    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    response = api.get('/api/v1/auth/profile/')

    assert response.status_code == 200
    assert response.data['data']['email'] == user.email
