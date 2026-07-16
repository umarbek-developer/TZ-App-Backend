from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.viewsets import ModelViewSet

from api.user.filters import PermissionFilter
from api.user.serializers.permission_serializers import PermissionSerializer
from apps.rbac.models import Permission
from apps.rbac.permissions import require_permissions

# Only the Admin role is seeded with these codes, so the catalogue is
# administrator-only in practice — an outcome of the RBAC tables rather than a
# hardcoded check.
CanViewPermissions = require_permissions('permission.view')
CanManagePermissions = require_permissions('permission.manage')

_UNAUTHORIZED = OpenApiResponse(description='No or invalid token.')
_FORBIDDEN = OpenApiResponse(description='Authenticated, but the required permission is missing.')

_FILTER_HELP = (
    'Filters: `?code=` (exact, case-insensitive), `?code_contains=`, '
    '`?namespace=user` (everything under `user.*`), `?name=`, `?role=<uuid>`, '
    '`?role_name=Manager`, `?unassigned=true`, `?created_after=`/`?created_before=`. '
    'Search: `?search=` across code, name and description. '
    'Ordering: `?ordering=code|name|created_at|updated_at`, prefix `-` to reverse. '
    'Pagination: `?page=`, `?page_size=`.'
)


@extend_schema_view(
    list=extend_schema(
        tags=['permissions'],
        summary='List permissions',
        description=f'Requires the `permission.view` permission.\n\n{_FILTER_HELP}',
        responses={200: PermissionSerializer(many=True), 401: _UNAUTHORIZED, 403: _FORBIDDEN},
    ),
    retrieve=extend_schema(
        tags=['permissions'],
        summary='Retrieve a permission',
        description='Requires the `permission.view` permission.',
        responses={
            200: PermissionSerializer,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
            404: OpenApiResponse(description='No permission with this id.'),
        },
    ),
    create=extend_schema(
        tags=['permissions'],
        summary='Create a permission',
        description=(
            'Requires the `permission.manage` permission. Codes are lowercased, must '
            'be dotted lowercase words, and are unique case-insensitively.'
        ),
        responses={
            201: PermissionSerializer,
            400: OpenApiResponse(description='Validation failed (duplicate or malformed code).'),
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
    ),
    update=extend_schema(
        tags=['permissions'],
        summary='Replace a permission',
        description='Requires the `permission.manage` permission.',
        responses={
            200: PermissionSerializer,
            400: OpenApiResponse(description='Validation failed.'),
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
    ),
    partial_update=extend_schema(
        tags=['permissions'],
        summary='Update a permission',
        description='Requires the `permission.manage` permission.',
        responses={
            200: PermissionSerializer,
            400: OpenApiResponse(description='Validation failed.'),
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
    ),
    destroy=extend_schema(
        tags=['permissions'],
        summary='Delete a permission',
        description=(
            'Requires the `permission.manage` permission. Deleting a permission also '
            'revokes it from every role that held it; the roles themselves survive. '
            'Any endpoint gated on the deleted code then denies everyone.'
        ),
        responses={
            204: OpenApiResponse(description='Deleted.'),
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
    ),
)
class PermissionViewSet(ModelViewSet):
    """CRUD over the permission catalogue, gated by the RBAC permission codes."""

    serializer_class = PermissionSerializer
    # prefetch_related: the serializer renders each permission's role names, which
    # would otherwise be one query per row on the list endpoint.
    queryset = Permission.objects.prefetch_related('roles').all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PermissionFilter
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'created_at', 'updated_at']
    ordering = ['code']

    permission_classes = [CanViewPermissions]

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [CanViewPermissions()]
        return [CanManagePermissions()]
