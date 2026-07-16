import pytest
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

URL = '/api/v1/auth/logout/'

pytestmark = pytest.mark.django_db


def test_logout_blacklists_the_refresh_token(auth_client, tokens):
    response = auth_client.post(URL, {'refresh': tokens['refresh']}, format='json')

    assert response.status_code == 205, response.data
    assert BlacklistedToken.objects.count() == 1


def test_blacklisted_refresh_token_cannot_be_reused(auth_client, tokens):
    auth_client.post(URL, {'refresh': tokens['refresh']}, format='json')

    # A blacklisted refresh token must no longer mint access tokens.
    with pytest.raises(TokenError):
        RefreshToken(tokens['refresh']).check_blacklist()


def test_logout_twice_is_rejected(auth_client, tokens):
    auth_client.post(URL, {'refresh': tokens['refresh']}, format='json')

    response = auth_client.post(URL, {'refresh': tokens['refresh']}, format='json')

    assert response.status_code == 400
    assert 'refresh' in response.data


def test_logout_rejects_garbage_token(auth_client):
    response = auth_client.post(URL, {'refresh': 'not-a-jwt'}, format='json')

    assert response.status_code == 400


def test_logout_requires_the_refresh_field(auth_client):
    response = auth_client.post(URL, {}, format='json')

    assert response.status_code == 400
    assert 'refresh' in response.data


def test_logout_without_authentication_is_401(api, tokens):
    response = api.post(URL, {'refresh': tokens['refresh']}, format='json')

    assert response.status_code == 401
