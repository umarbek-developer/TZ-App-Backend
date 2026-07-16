import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.rbac.permissions import HasPermission, require_permissions
from apps.users.models import User

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


# --- throwaway views (this step ships no real APIs) --------------------------


class MockView(APIView):
    """Requires a single code, declared inline via the factory."""

    permission_classes = [require_permissions('mock.view')]

    def get(self, request):
        return Response({'ok': True})


class ViewAttrView(APIView):
    """Requires a code declared on the view instead."""

    permission_classes = [HasPermission]
    required_permissions = 'role.view'

    def get(self, request):
        return Response({'ok': True})


class RequireAllView(APIView):
    permission_classes = [require_permissions('role.view', 'role.manage')]

    def get(self, request):
        return Response({'ok': True})


class RequireAnyView(APIView):
    permission_classes = [require_permissions('role.view', 'role.manage', require_all=False)]

    def get(self, request):
        return Response({'ok': True})


class MisconfiguredView(APIView):
    """Asks for HasPermission but names no code — a programming error."""

    permission_classes = [HasPermission]

    def get(self, request):
        return Response({'ok': True})


# --- helpers -----------------------------------------------------------------


def make_user(email='rbac@gmail.com', is_active=True):
    return User.objects.create_user(
        email=email, password='Password123!', first_name='R', is_active=is_active
    )


def grant(user, role_name, *codes):
    role, _ = Role.objects.get_or_create(name=role_name)
    UserRole.objects.get_or_create(user=user, role=role)
    for code in codes:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={'name': code})
        RolePermission.objects.get_or_create(role=role, permission=permission)
    return role


def call(view, user=None):
    request = factory.get('/')
    if user is not None:
        force_authenticate(request, user=user)
    return view.as_view()(request)


@pytest.fixture
def user():
    return make_user()


# --- the three behaviours ----------------------------------------------------


def test_anonymous_gets_401():
    assert call(MockView).status_code == 401


def test_authenticated_without_permission_gets_403(user):
    assert call(MockView, user).status_code == 403


def test_authenticated_with_permission_is_allowed(user):
    grant(user, 'Employee', 'mock.view')

    response = call(MockView, user)

    assert response.status_code == 200
    assert response.data == {'ok': True}


def test_role_without_the_code_gets_403(user):
    grant(user, 'Guest')

    assert call(MockView, user).status_code == 403


def test_holding_a_different_code_gets_403(user):
    grant(user, 'Manager', 'user.view')

    assert call(MockView, user).status_code == 403


def test_403_body_names_the_missing_permission(user):
    response = call(MockView, user)

    assert 'mock.view' in response.data['message']


# --- multiple roles ----------------------------------------------------------


def test_permission_from_the_second_of_several_roles_is_honoured(user):
    grant(user, 'Guest')
    grant(user, 'Manager', 'user.view')
    grant(user, 'Employee', 'mock.view')

    assert call(MockView, user).status_code == 200


def test_permission_split_across_two_roles_satisfies_require_all(user):
    grant(user, 'Viewer', 'role.view')
    grant(user, 'Editor', 'role.manage')

    assert call(RequireAllView, user).status_code == 200


def test_require_all_denies_a_partial_match(user):
    grant(user, 'Viewer', 'role.view')

    assert call(RequireAllView, user).status_code == 403


def test_require_any_allows_a_partial_match(user):
    grant(user, 'Viewer', 'role.view')

    assert call(RequireAnyView, user).status_code == 200


def test_require_any_denies_when_nothing_matches(user):
    grant(user, 'Employee', 'mock.view')

    assert call(RequireAnyView, user).status_code == 403


# --- declaration styles ------------------------------------------------------


def test_codes_declared_on_the_view_are_honoured(user):
    grant(user, 'Viewer', 'role.view')

    assert call(ViewAttrView, user).status_code == 200


def test_codes_declared_on_the_view_still_deny(user):
    assert call(ViewAttrView, user).status_code == 403


def test_view_attribute_style_is_401_for_anonymous():
    assert call(ViewAttrView).status_code == 401


# --- inactive users ----------------------------------------------------------


def test_inactive_user_is_denied_even_holding_the_code():
    user = make_user(is_active=False)
    grant(user, 'Employee', 'mock.view')

    # force_authenticate bypasses SimpleJWT's own is_active check, so this asserts
    # the services layer independently refuses a deactivated account.
    assert call(MockView, user).status_code == 403


# --- misconfiguration --------------------------------------------------------


def test_missing_codes_deny_rather_than_allow(user, caplog):
    """A view that names no code is a programming error, and must never fall open.

    Since the project-wide exception handler was added, the ImproperlyConfigured is
    caught and reported as a 500 rather than propagating — so the guarantee is now
    "the request fails and is logged", not "an exception escapes". Either way the
    caller does not get in.
    """
    grant(user, 'Admin', 'mock.view')

    response = call(MisconfiguredView, user)

    assert response.status_code == 500
    assert response.data['success'] is False
    assert 'declares no permission codes' in caplog.text


def test_factory_rejects_no_codes():
    with pytest.raises(ImproperlyConfigured, match='at least one permission code'):
        require_permissions()


def test_factory_rejects_a_list_argument():
    # require_permissions(['a', 'b']) is an easy slip; it must not silently build a
    # class whose "code" is a list object that can never match.
    with pytest.raises(ImproperlyConfigured, match='as strings'):
        require_permissions(['role.view'])


# --- reusability -------------------------------------------------------------


def test_factory_builds_independent_classes():
    a = require_permissions('mock.view')
    b = require_permissions('role.view')

    assert a is not b
    assert a.required_permissions == ('mock.view',)
    assert b.required_permissions == ('role.view',)
    assert issubclass(a, HasPermission)


def test_same_class_is_reusable_across_views(user):
    grant(user, 'Employee', 'mock.view')
    shared = require_permissions('mock.view')

    class First(APIView):
        permission_classes = [shared]

        def get(self, request):
            return Response({'view': 'first'})

    class Second(APIView):
        permission_classes = [shared]

        def get(self, request):
            return Response({'view': 'second'})

    assert call(First, user).status_code == 200
    assert call(Second, user).status_code == 200


# --- query efficiency --------------------------------------------------------


def test_a_permitted_request_costs_one_permission_query(user, django_assert_num_queries):
    grant(user, 'Employee', 'mock.view')
    grant(user, 'Manager', 'user.view')

    # force_authenticate hands the view a live user object, so the only query the
    # request needs is the permission resolution itself.
    with django_assert_num_queries(1):
        assert call(MockView, user).status_code == 200


def test_a_denied_request_costs_one_permission_query(user, django_assert_num_queries):
    with django_assert_num_queries(1):
        assert call(MockView, user).status_code == 403


def test_an_anonymous_request_costs_no_queries(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert call(MockView).status_code == 401
