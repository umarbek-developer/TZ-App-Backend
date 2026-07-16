"""Reusable DRF permission classes backed by the RBAC tables.

Usage — either declare the codes on the view:

    class RoleListView(APIView):
        permission_classes = [HasPermission]
        required_permissions = 'role.view'

or build the class inline, which reads better for one-off endpoints:

    class MockProjectsView(APIView):
        permission_classes = [require_permissions('mock.view')]

Status codes are DRF's own doing and come out right for free: when a permission
class returns False, DRF raises NotAuthenticated (-> 401) if the request carried no
successful authenticator, and PermissionDenied (-> 403) if it did. That mapping only
holds while the view keeps an authenticator that can emit a WWW-Authenticate header
(JWTAuthentication does); a view with `authentication_classes = []` collapses both
cases to 403.
"""

from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import BasePermission

from apps.rbac.services import get_user_permission_codes


class HasPermission(BasePermission):
    """Allows the request when the user holds the view's required permission codes.

    Reads codes from `required_permissions` — on the class (set by
    `require_permissions()`) or on the view. A single string or any iterable of
    strings is accepted. By default every listed code must be held; set
    `require_all = False` for any-of semantics.
    """

    required_permissions = ()
    require_all = True
    message = 'You do not have permission to perform this action.'

    def get_required_permissions(self, view):
        codes = self.required_permissions or getattr(view, 'required_permissions', None)

        # Fail loudly rather than open. A view that asks for HasPermission but names
        # no code is a programming error; silently allowing every authenticated user
        # would be a quiet authorisation hole.
        if not codes:
            raise ImproperlyConfigured(
                f'{view.__class__.__name__} uses {self.__class__.__name__} but declares no '
                f'permission codes. Set `required_permissions` on the view, or use '
                f'require_permissions("some.code"). For an endpoint that needs only a '
                f'logged-in user, use IsAuthenticated instead.'
            )

        if isinstance(codes, str):
            return (codes,)
        return tuple(codes)

    def has_permission(self, request, view):
        required = self.get_required_permissions(view)

        user = request.user
        if not (user and user.is_authenticated):
            # -> 401. DRF distinguishes this from the authenticated-but-denied case.
            return False

        held = get_user_permission_codes(user)
        if self.require_all:
            return held.issuperset(required)
        return bool(held & set(required))

    def has_object_permission(self, request, view, obj):
        # These grants are global rather than per-object; object-level checks reuse
        # the same answer (and the same cached code set).
        return self.has_permission(request, view)


def require_permissions(*codes, require_all=True):
    """Build a `HasPermission` subclass bound to `codes`.

    DRF instantiates each entry in `permission_classes`, so it needs classes, not
    instances — hence a factory rather than `HasPermission('mock.view')`.

        permission_classes = [require_permissions('mock.view')]
        permission_classes = [require_permissions('role.view', 'role.manage')]
        permission_classes = [require_permissions('a', 'b', require_all=False)]
    """
    if not codes:
        raise ImproperlyConfigured('require_permissions() needs at least one permission code.')

    flat = []
    for code in codes:
        if not isinstance(code, str):
            raise ImproperlyConfigured(
                f'require_permissions() takes permission codes as strings, got {code!r}. '
                f'Pass them as separate arguments: require_permissions("a", "b").'
            )
        flat.append(code)

    joiner = ' and ' if require_all else ' or '
    return type(
        'HasPermission_' + '_'.join(c.replace('.', '_') for c in flat),
        (HasPermission,),
        {
            'required_permissions': tuple(flat),
            'require_all': require_all,
            'message': f'This action requires the {joiner.join(flat)} permission.',
            '__doc__': f'Requires the {joiner.join(flat)} permission code(s).',
        },
    )
