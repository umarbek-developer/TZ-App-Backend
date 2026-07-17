import pytest
from django.http import Http404
from rest_framework import serializers, status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.users.models import User

factory = APIRequestFactory()

ERROR_KEYS = {'success', 'message', 'errors'}
SUCCESS_KEYS = {'success', 'message', 'data'}


# --- throwaway views, one per failure mode -----------------------------------


class RaisingView(APIView):
    """Raises whatever `exc` is set to. Public, so permissions never interfere."""

    permission_classes = [AllowAny]
    exc = None

    def get(self, request):
        raise self.exc


def raising(exception):
    return type('_V', (RaisingView,), {'exc': exception})


class FieldValidationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raise ValidationError({'email': ['This field is required.']})


class ListValidationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # A serializer-level error: DRF hands back a bare list, not a dict.
        raise ValidationError(['Something is wrong overall.'])


class StringValidationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raise ValidationError('Plain string detail.')


class SerializerView(APIView):
    """The realistic path: is_valid(raise_exception=True)."""

    permission_classes = [AllowAny]

    class Body(serializers.Serializer):
        email = serializers.EmailField()
        age = serializers.IntegerField(min_value=0)

    def post(self, request):
        serializer = self.Body(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'ok': True})


class BoomView(APIView):
    """An honest bug."""

    permission_classes = [AllowAny]

    def get(self, request):
        raise ValueError('something went very wrong internally')


def call(view, method='get', data=None, user=None):
    request = getattr(factory, method)('/', data, format='json')
    if user is not None:
        force_authenticate(request, user=user)
    response = view.as_view()(request)
    # APIRequestFactory hands back an unrendered response. The success envelope is
    # applied by the renderer, so without this the assertions would inspect the bare
    # payload — something no client ever receives. (Errors need no render: the
    # exception handler writes response.data itself.)
    response.render()
    return response


# --- the envelope ------------------------------------------------------------


@pytest.mark.parametrize(
    'exception,expected_status',
    [
        (NotAuthenticated(), status.HTTP_401_UNAUTHORIZED),
        (AuthenticationFailed(), status.HTTP_401_UNAUTHORIZED),
        (PermissionDenied(), status.HTTP_403_FORBIDDEN),
        (NotFound(), status.HTTP_404_NOT_FOUND),
        (Http404(), status.HTTP_404_NOT_FOUND),
        (ValidationError('bad'), status.HTTP_400_BAD_REQUEST),
    ],
)
def test_every_error_uses_the_same_envelope(exception, expected_status):
    response = call(raising(exception))

    assert response.status_code == expected_status
    assert set(response.data) == ERROR_KEYS
    assert response.data['success'] is False
    assert isinstance(response.data['message'], str)
    assert response.data['message']
    assert isinstance(response.data['errors'], dict)


def test_success_responses_get_the_success_envelope():
    """Errors and successes are shaped by different machinery — the exception
    handler for one, the renderer for the other — but both come out enveloped."""
    response = call(SerializerView, 'post', {'email': 'a@b.com', 'age': 1})

    assert response.status_code == 200
    assert set(response.data) == SUCCESS_KEYS
    assert response.data['success'] is True
    assert response.data['data'] == {'ok': True}


# --- ValidationError ---------------------------------------------------------


def test_field_errors_land_under_errors():
    response = call(FieldValidationView, 'post', {})

    assert response.status_code == 400
    assert response.data['message'] == 'Validation failed.'
    assert response.data['errors'] == {'email': ['This field is required.']}


def test_serializer_errors_land_under_errors():
    response = call(SerializerView, 'post', {'email': 'not-an-email', 'age': -1})

    assert response.status_code == 400
    assert set(response.data['errors']) == {'email', 'age'}


def test_a_bare_list_error_is_filed_under_non_field_errors():
    """DRF returns a list for serializer-level errors; the envelope promises a dict."""
    response = call(ListValidationView, 'post', {})

    assert response.status_code == 400
    assert response.data['errors'] == {'non_field_errors': ['Something is wrong overall.']}


def test_a_string_error_is_filed_under_non_field_errors():
    response = call(StringValidationView, 'post', {})

    assert response.status_code == 400
    assert response.data['errors'] == {'non_field_errors': ['Plain string detail.']}


def test_validation_errors_are_json_serialisable():
    """ErrorDetail is a str subclass; make sure nothing exotic leaks into the body."""
    import json

    response = call(SerializerView, 'post', {'email': 'nope', 'age': 'x'})
    response.render()

    assert set(json.loads(response.content)) == ERROR_KEYS


# --- authentication / permissions --------------------------------------------


def test_not_authenticated_keeps_its_message():
    response = call(raising(NotAuthenticated()))

    assert response.status_code == 401
    assert response.data['message'] == 'Authentication credentials were not provided.'
    assert response.data['errors'] == {}


def test_authentication_failed_keeps_its_message():
    response = call(raising(AuthenticationFailed('Token is invalid.')))

    assert response.status_code == 401
    assert response.data['message'] == 'Token is invalid.'


def test_permission_denied_keeps_its_message():
    response = call(raising(PermissionDenied('Nope, not you.')))

    assert response.status_code == 403
    assert response.data['message'] == 'Nope, not you.'
    assert response.data['errors'] == {}


def test_the_401_www_authenticate_header_survives_reshaping(db):
    """The handler rebuilds `data`, never the Response.

    DRF decides 401-vs-403 by whether it can build a WWW-Authenticate header. A
    handler that returned a fresh Response would drop the header and silently turn
    every 401 into a 403.
    """
    from api.auth.views.profile_views import ProfileView

    response = ProfileView.as_view()(factory.get('/'))

    assert response.status_code == 401
    assert 'WWW-Authenticate' in response


def test_403_is_still_distinguishable_from_401(db):
    from api.auth.views.profile_views import ProfileView

    user = User.objects.create_user(
        email='envelope@test.com', password='Password123!', first_name='E', is_active=True
    )

    anonymous = ProfileView.as_view()(factory.get('/'))
    request = factory.get('/')
    force_authenticate(request, user=user)
    authenticated = ProfileView.as_view()(request)

    assert anonymous.status_code == 401
    assert authenticated.status_code == 200


# --- 404 ---------------------------------------------------------------------


def test_http404_is_reshaped():
    response = call(raising(Http404()))

    assert response.status_code == 404
    assert response.data == {'success': False, 'message': 'Not found.', 'errors': {}}


def test_notfound_keeps_its_message():
    response = call(raising(NotFound('No role with this id.')))

    assert response.status_code == 404
    assert response.data['message'] == 'No role with this id.'


# --- 500 ---------------------------------------------------------------------


def test_an_unhandled_exception_becomes_a_json_500():
    response = call(BoomView)

    assert response.status_code == 500
    assert set(response.data) == ERROR_KEYS
    assert response.data['success'] is False


def test_a_500_does_not_leak_internals():
    """The body must say nothing about what actually broke."""
    response = call(BoomView)

    body = str(response.data).lower()
    assert 'something went very wrong internally' not in body
    assert 'valueerror' not in body
    assert 'traceback' not in body
    assert response.data['message'] == 'Internal server error.'


def test_a_500_logs_the_traceback(caplog):
    """The body says nothing, so the log is the only record — it must be there."""
    call(BoomView)

    assert 'Unhandled exception' in caplog.text
    assert 'ValueError' in caplog.text
    assert 'something went very wrong internally' in caplog.text


def test_the_500_log_names_the_view(caplog):
    call(BoomView)

    assert 'BoomView' in caplog.text


# --- other DRF exceptions ride the same envelope -----------------------------


def test_method_not_allowed_uses_the_envelope():
    response = call(SerializerView, 'get')

    assert response.status_code == 405
    assert set(response.data) == ERROR_KEYS
    assert response.data['success'] is False
