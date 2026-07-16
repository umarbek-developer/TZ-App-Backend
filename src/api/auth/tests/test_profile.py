import pytest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.users.models import User

from .conftest import PASSWORD

URL = '/api/v1/auth/profile/'

pytestmark = pytest.mark.django_db


# --- GET ---------------------------------------------------------------------


def test_get_profile_returns_current_user(auth_client, user):
    response = auth_client.get(URL)

    assert response.status_code == 200, response.data
    assert response.data['email'] == user.email
    assert response.data['first_name'] == 'John'
    assert response.data['middle_name'] == 'Smith'


def test_get_profile_never_exposes_the_password(auth_client):
    response = auth_client.get(URL)

    assert 'password' not in response.data


def test_get_profile_without_token_is_401(api):
    response = api.get(URL)

    assert response.status_code == 401


def test_get_profile_with_garbage_token_is_401(api):
    api.credentials(HTTP_AUTHORIZATION='Bearer not-a-jwt')

    response = api.get(URL)

    assert response.status_code == 401


# --- PATCH -------------------------------------------------------------------


def test_patch_updates_profile_fields(auth_client, user):
    response = auth_client.patch(URL, {'first_name': 'Jane'}, format='json')

    assert response.status_code == 200, response.data
    assert response.data['first_name'] == 'Jane'
    user.refresh_from_db()
    assert user.first_name == 'Jane'


def test_patch_can_change_email(auth_client, user):
    response = auth_client.patch(URL, {'email': 'new@gmail.com'}, format='json')

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.email == 'new@gmail.com'


def test_patch_rejects_an_email_taken_by_someone_else(auth_client, user):
    User.objects.create_user(email='taken@gmail.com', password=PASSWORD, first_name='X')

    response = auth_client.patch(URL, {'email': 'taken@gmail.com'}, format='json')

    assert response.status_code == 400
    assert 'email' in response.data


def test_patch_cannot_reactivate_via_is_active(auth_client, user):
    # is_active is the soft-delete flag; a writable one would let a deleted user
    # resurrect their own account.
    response = auth_client.patch(URL, {'is_active': False}, format='json')

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_active is True


def test_patch_does_not_corrupt_the_password_hash(auth_client, user):
    original = user.password

    auth_client.patch(URL, {'first_name': 'Jane'}, format='json')

    user.refresh_from_db()
    assert user.password == original
    assert user.check_password(PASSWORD)


def test_patch_without_token_is_401(api):
    response = api.patch(URL, {'first_name': 'Jane'}, format='json')

    assert response.status_code == 401


# --- DELETE ------------------------------------------------------------------


def test_delete_soft_deletes_the_user(auth_client, user):
    response = auth_client.delete(URL)

    assert response.status_code == 204
    user.refresh_from_db()
    assert user.is_active is False
    # Soft delete: the row must survive.
    assert User.objects.filter(pk=user.pk).exists()


def test_delete_blacklists_outstanding_refresh_tokens(auth_client, user):
    auth_client.delete(URL)

    assert BlacklistedToken.objects.filter(token__user=user).exists()


def test_access_token_stops_working_after_delete(auth_client):
    auth_client.delete(URL)

    # Same client, same access token — SimpleJWT rejects it because the user is
    # now inactive (CHECK_USER_IS_ACTIVE).
    response = auth_client.get(URL)

    assert response.status_code == 401


def test_deleted_user_cannot_log_in_again(api, auth_client, user):
    auth_client.delete(URL)

    response = api.post(
        '/api/v1/auth/login/',
        {'email': user.email, 'password': PASSWORD},
        format='json',
    )

    assert response.status_code == 401


def test_delete_without_token_is_401(api):
    response = api.delete(URL)

    assert response.status_code == 401
