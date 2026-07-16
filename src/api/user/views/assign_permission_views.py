from django.db import transaction
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.user.serializers.assign_permission_serializers import (
    AssignPermissionResponseSerializer,
    AssignPermissionSerializer,
    RemovePermissionsResponseSerializer,
    ReplacePermissionsResponseSerializer,
    ReplacePermissionsSerializer,
    RoleBriefSerializer,
)
from apps.rbac.models import RolePermission
from apps.rbac.permissions import require_permissions
from apps.rbac.services import clear_permission_cache

# Editing what a role carries is a permission-management action, so it rides the
# same code as writing the catalogue. Only the seeded Admin role holds it.
CanManagePermissions = require_permissions('permission.manage')

_UNAUTHORIZED = OpenApiResponse(description='No or invalid token.')
_FORBIDDEN = OpenApiResponse(description='Authenticated, but `permission.manage` is missing.')
_BAD_REQUEST = OpenApiResponse(
    description=(
        'Validation failed: unknown role or permission id, duplicate ids, or an empty '
        'permission list.'
    )
)

_IMMEDIACY_NOTE = (
    'Takes effect immediately: every user holding this role sees the change on their '
    'very next request, with no re-login and no token refresh. Permission codes are '
    'resolved from the database per request and only memoised for the life of that '
    'request.'
)

_REQUEST_EXAMPLE = OpenApiExample(
    'Grant two permissions',
    value={
        'role': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
        'permissions': [
            '1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed',
            '7c9e6679-7425-40de-944b-e07fc1f90ae7',
        ],
    },
    request_only=True,
)


def _codes(permissions):
    return sorted(permission.code for permission in permissions)


def _current_codes(role):
    return sorted(
        RolePermission.objects.filter(role=role).values_list('permission__code', flat=True)
    )


def _payload(role, **buckets):
    body = {'role': RoleBriefSerializer(role).data, 'permissions': _current_codes(role)}
    body.update(buckets)
    return body


@extend_schema_view(
    post=extend_schema(
        tags=['assign'],
        summary='Assign permissions to a role',
        description=(
            'Adds the given permissions to the role, keeping any it already carries. '
            f'Requires `permission.manage`.\n\n{_IMMEDIACY_NOTE}\n\n'
            'Idempotent: granting a permission the role already has is a no-op rather '
            'than an error, and is reported under `already_assigned`.'
        ),
        request=AssignPermissionSerializer,
        responses={
            200: AssignPermissionResponseSerializer,
            400: _BAD_REQUEST,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
        examples=[_REQUEST_EXAMPLE],
    ),
    put=extend_schema(
        tags=['assign'],
        summary="Replace a role's permissions",
        description=(
            'Sets the role to carry exactly the given permissions, adding what is '
            f'missing and revoking everything else. Requires `permission.manage`.\n\n'
            f'{_IMMEDIACY_NOTE}\n\n'
            'An empty `permissions` list strips every permission — unlike POST and '
            'DELETE, which reject it.'
        ),
        request=ReplacePermissionsSerializer,
        responses={
            200: ReplacePermissionsResponseSerializer,
            400: _BAD_REQUEST,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
        examples=[_REQUEST_EXAMPLE],
    ),
    delete=extend_schema(
        tags=['assign'],
        summary='Remove permissions from a role',
        description=(
            'Revokes the given permissions from the role, leaving the rest. Requires '
            f'`permission.manage`.\n\n{_IMMEDIACY_NOTE}\n\n'
            'Idempotent: removing a permission the role does not carry is a no-op '
            'rather than an error, and is reported under `not_assigned`.'
        ),
        request=AssignPermissionSerializer,
        responses={
            200: RemovePermissionsResponseSerializer,
            400: _BAD_REQUEST,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
        examples=[_REQUEST_EXAMPLE],
    ),
)
class AssignPermissionView(APIView):
    """Grant, replace and revoke the permissions a role carries."""

    permission_classes = [CanManagePermissions]

    def _validated(self, request, serializer_class):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data['role'], serializer.validated_data['permissions']

    def _invalidate(self, request):
        # Other users re-resolve from the database on their next request, so nothing
        # to do for them. The caller is the one live user object in this process, and
        # they may well have just edited their own role.
        clear_permission_cache(request.user)

    @transaction.atomic
    def post(self, request):
        role, permissions = self._validated(request, AssignPermissionSerializer)

        held = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        added = [p for p in permissions if p.pk not in held]
        already = [p for p in permissions if p.pk in held]

        RolePermission.objects.bulk_create(
            [RolePermission(role=role, permission=p) for p in added],
            # Belt and braces against a concurrent identical request: the unique
            # constraint would otherwise turn a duplicate into a 500.
            ignore_conflicts=True,
        )
        self._invalidate(request)

        return Response(
            _payload(role, added=_codes(added), already_assigned=_codes(already)),
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def put(self, request):
        role, permissions = self._validated(request, ReplacePermissionsSerializer)

        held = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        wanted = {p.pk: p for p in permissions}

        added = [p for pk, p in wanted.items() if pk not in held]
        unchanged = [p for pk, p in wanted.items() if pk in held]
        removed_qs = RolePermission.objects.filter(role=role).exclude(permission_id__in=wanted)
        removed = sorted(removed_qs.values_list('permission__code', flat=True))

        removed_qs.delete()
        RolePermission.objects.bulk_create(
            [RolePermission(role=role, permission=p) for p in added],
            ignore_conflicts=True,
        )
        self._invalidate(request)

        return Response(
            _payload(
                role,
                added=_codes(added),
                removed=removed,
                unchanged=_codes(unchanged),
            ),
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def delete(self, request):
        role, permissions = self._validated(request, AssignPermissionSerializer)

        held = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        removed = [p for p in permissions if p.pk in held]
        not_assigned = [p for p in permissions if p.pk not in held]

        RolePermission.objects.filter(
            role=role, permission_id__in=[p.pk for p in removed]
        ).delete()
        self._invalidate(request)

        return Response(
            _payload(role, removed=_codes(removed), not_assigned=_codes(not_assigned)),
            status=status.HTTP_200_OK,
        )
