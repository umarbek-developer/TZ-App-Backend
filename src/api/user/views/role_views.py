from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.viewsets import ModelViewSet

from api.user.serializers.role_serializers import RoleSerializer
from apps.rbac.models import Role
from apps.rbac.permissions import require_permissions

# Built once at import rather than per request. Only the Admin role is seeded with
# these codes, so in practice these endpoints are administrator-only — but that
# falls out of the RBAC tables rather than being hardcoded here, so granting
# role.view to another role is enough to open up reads.
CanViewRoles = require_permissions('role.view')
CanManageRoles = require_permissions('role.manage')

_UNAUTHORIZED = OpenApiResponse(description='No or invalid token.')
_FORBIDDEN = OpenApiResponse(description='Authenticated, but the required permission is missing.')


@extend_schema_view(
    list=extend_schema(
        tags=['roles'],
        summary='List roles',
        description=(
            'Requires the `role.view` permission. Supports pagination '
            '(`?page=`, `?page_size=`), search over name and description '
            '(`?search=`), and ordering (`?ordering=name|created_at|updated_at`, '
            'prefix with `-` to reverse).'
        ),
        responses={200: RoleSerializer(many=True), 401: _UNAUTHORIZED, 403: _FORBIDDEN},
    ),
    retrieve=extend_schema(
        tags=['roles'],
        summary='Retrieve a role',
        description='Requires the `role.view` permission.',
        responses={200: RoleSerializer, 401: _UNAUTHORIZED, 403: _FORBIDDEN, 404: OpenApiResponse(
            description='No role with this id.'
        )},
    ),
    create=extend_schema(
        tags=['roles'],
        summary='Create a role',
        description='Requires the `role.manage` permission. Names are unique, case-insensitively.',
        responses={
            201: RoleSerializer,
            400: OpenApiResponse(description='Validation failed (duplicate or blank name).'),
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
    ),
    update=extend_schema(
        tags=['roles'],
        summary='Replace a role',
        description='Requires the `role.manage` permission.',
        responses={200: RoleSerializer, 400: OpenApiResponse(description='Validation failed.'),
                   401: _UNAUTHORIZED, 403: _FORBIDDEN},
    ),
    partial_update=extend_schema(
        tags=['roles'],
        summary='Update a role',
        description='Requires the `role.manage` permission.',
        responses={200: RoleSerializer, 400: OpenApiResponse(description='Validation failed.'),
                   401: _UNAUTHORIZED, 403: _FORBIDDEN},
    ),
    destroy=extend_schema(
        tags=['roles'],
        summary='Delete a role',
        description=(
            'Requires the `role.manage` permission. Deleting a role also removes its '
            'permission grants and revokes it from every user who held it; the users '
            'and permissions themselves are untouched.'
        ),
        responses={204: OpenApiResponse(description='Deleted.'), 401: _UNAUTHORIZED,
                   403: _FORBIDDEN},
    ),
)
class RoleViewSet(ModelViewSet):
    """CRUD over roles, gated by the RBAC permission codes."""

    serializer_class = RoleSerializer
    # prefetch_related: the serializer renders each role's permission codes, which
    # would otherwise be one query per row on the list endpoint.
    queryset = Role.objects.prefetch_related('permissions').all()

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']

    # Reads and writes are gated separately; see get_permissions. This attribute is
    # the default and what drf-spectacular introspects.
    permission_classes = [CanViewRoles]

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [CanViewRoles()]
        return [CanManageRoles()]
