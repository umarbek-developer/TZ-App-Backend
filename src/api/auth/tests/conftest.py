import pytest
from rest_framework.test import APIClient

from apps.users.models import User

PASSWORD = 'Password123!'


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user_data():
    return {
        'first_name': 'John',
        'last_name': 'Doe',
        'middle_name': 'Smith',
        'email': 'john@gmail.com',
        'password': PASSWORD,
        'confirm_password': PASSWORD,
    }


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='john@gmail.com',
        password=PASSWORD,
        first_name='John',
        last_name='Doe',
        middle_name='Smith',
        is_active=True,
    )


@pytest.fixture
def inactive_user(db):
    return User.objects.create_user(
        email='ghost@gmail.com',
        password=PASSWORD,
        first_name='Ghost',
        last_name='User',
        is_active=False,
    )


@pytest.fixture
def tokens(api, user):
    """Log in through the real endpoint so tests exercise the issued tokens."""
    response = api.post(
        '/api/v1/auth/login/',
        {'email': user.email, 'password': PASSWORD},
        format='json',
    )
    assert response.status_code == 200, response.data
    # The body is enveloped; the token pair lives under `data`.
    return response.data['data']


@pytest.fixture
def auth_client(api, tokens):
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    return api
