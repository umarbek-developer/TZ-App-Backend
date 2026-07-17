import pytest

from apps.users.models import User

from .conftest import PASSWORD

URL = '/api/v1/auth/register/'

pytestmark = pytest.mark.django_db


def test_register_creates_active_user(api, user_data):
    response = api.post(URL, user_data, format='json')

    assert response.status_code == 201, response.data
    user = User.objects.get(email='john@gmail.com')
    assert user.first_name == 'John'
    assert user.middle_name == 'Smith'
    # The model defaults is_active to False; registration must override it or the
    # new account could never log in.
    assert user.is_active is True


def test_register_hashes_the_password(api, user_data):
    api.post(URL, user_data, format='json')

    user = User.objects.get(email='john@gmail.com')
    assert user.password != PASSWORD
    assert user.password.startswith('pbkdf2_sha256$')
    assert user.check_password(PASSWORD)


def test_register_never_returns_the_password(api, user_data):
    response = api.post(URL, user_data, format='json')

    assert 'password' not in response.data['data']
    assert 'confirm_password' not in response.data['data']


def test_register_rejects_mismatched_confirmation(api, user_data):
    user_data['confirm_password'] = 'Different123!'

    response = api.post(URL, user_data, format='json')

    assert response.status_code == 400
    assert 'confirm_password' in response.data['errors']
    assert not User.objects.filter(email='john@gmail.com').exists()


def test_register_rejects_duplicate_email(api, user, user_data):
    response = api.post(URL, user_data, format='json')

    assert response.status_code == 400
    assert 'email' in response.data['errors']
    assert User.objects.filter(email__iexact='john@gmail.com').count() == 1


def test_register_rejects_duplicate_email_case_insensitively(api, user, user_data):
    user_data['email'] = 'JOHN@GMAIL.COM'

    response = api.post(URL, user_data, format='json')

    assert response.status_code == 400
    assert 'email' in response.data['errors']


def test_register_rejects_weak_password(api, user_data):
    user_data['password'] = user_data['confirm_password'] = 'abc'

    response = api.post(URL, user_data, format='json')

    assert response.status_code == 400
    assert 'password' in response.data['errors']


def test_register_rejects_missing_email(api, user_data):
    del user_data['email']

    response = api.post(URL, user_data, format='json')

    assert response.status_code == 400
    assert 'email' in response.data['errors']


def test_registered_user_can_log_in(api, user_data):
    api.post(URL, user_data, format='json')

    response = api.post(
        '/api/v1/auth/login/',
        {'email': user_data['email'], 'password': PASSWORD},
        format='json',
    )

    assert response.status_code == 200
    assert 'access' in response.data['data']
