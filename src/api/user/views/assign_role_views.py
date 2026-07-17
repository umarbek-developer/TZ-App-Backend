from django.db import transaction
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.user.serializers.assign_role_serializers import (
    AssignRoleResponseSerializer,
    AssignRoleSerializer,
    RemoveRolesResponseSerializer,
    ReplaceRolesResponseSerializer,
    ReplaceRolesSerializer,
    UserBriefSerializer,
)
from apps.rbac.models import UserRole
from apps.rbac.permissions import require_permissions
from apps.rbac.services import clear_permission_cache

# Assignment is a role-management action, so it rides the same code as writing
# roles themselves. Only the seeded Admin role holds it.
CanManageRoles = require_permissions('role.manage')

_UNAUTHORIZED = OpenApiResponse(description='No or invalid token.')
_FORBIDDEN = OpenApiResponse(description='Authenticated, but `role.manage` is missing.')
_BAD_REQUEST = OpenApiResponse(
    description='Validation failed: unknown user or role id, duplicate ids, or an empty role list.'
)

_REQUEST_EXAMPLE = OpenApiExample(
    'Assign two roles',
    value={
        'user': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
        'roles': [
            '1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed',
            '7c9e6679-7425-40de-944b-e07fc1f90ae7',
        ],
    },
    request_only=True,
)


def _names(roles):
    return sorted(role.name for role in roles)


def _current_roles(user):
    return sorted(
        UserRole.objects.filter(user=user).values_list('role__name', flat=True)
    )


def _payload(user, **buckets):
    body = {'user': UserBriefSerializer(user).data, 'roles': _current_roles(user)}
    body.update(buckets)
    return body


@extend_schema_view(
    post=extend_schema(
        tags=['assign'],
        summary='Assign roles to a user',
        description=(
            'Adds the given roles to the user, keeping any they already hold. '
            'Requires `role.manage`.\n\n'
            'Idempotent: assigning a role the user already has is a no-op rather than '
            'an error, and is reported under `already_assigned`.'
        ),
        request=AssignRoleSerializer,
        responses={
            200: AssignRoleResponseSerializer,
            400: _BAD_REQUEST,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
        examples=[_REQUEST_EXAMPLE],
    ),
    put=extend_schema(
        tags=['assign'],
        summary='Replace a user\'s roles',
        description=(
            'Sets the user\'s roles to exactly the given list, adding what is missing '
            'and revoking everything else. Requires `role.manage`.\n\n'
            'An empty `roles` list strips every role — unlike POST and DELETE, which '
            'reject it.'
        ),
        request=ReplaceRolesSerializer,
        responses={
            200: ReplaceRolesResponseSerializer,
            400: _BAD_REQUEST,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
        examples=[_REQUEST_EXAMPLE],
    ),
    delete=extend_schema(
        tags=['assign'],
        summary='Remove roles from a user',
        description=(
            'Revokes the given roles from the user, leaving the rest. Requires '
            '`role.manage`.\n\n'
            'Idempotent: removing a role the user does not hold is a no-op rather than '
            'an error, and is reported under `not_assigned`.'
        ),
        request=AssignRoleSerializer,
        responses={
            200: RemoveRolesResponseSerializer,
            400: _BAD_REQUEST,
            401: _UNAUTHORIZED,
            403: _FORBIDDEN,
        },
        examples=[_REQUEST_EXAMPLE],
    ),
)
class AssignRoleView(APIView):
    """Grant, replace and revoke a user's roles."""

    permission_classes = [CanManageRoles]

    def _validated(self, request, serializer_class):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data['user'], serializer.validated_data['roles']

    @transaction.atomic
    def post(self, request):
        user, roles = self._validated(request, AssignRoleSerializer)

        held = set(UserRole.objects.filter(user=user).values_list('role_id', flat=True))
        added = [role for role in roles if role.pk not in held]
        already = [role for role in roles if role.pk in held]

        UserRole.objects.bulk_create(
            [UserRole(user=user, role=role) for role in added],
            # Belt and braces against a concurrent identical request: the unique
            # constraint would otherwise turn a duplicate into a 500.
            ignore_conflicts=True,
        )
        clear_permission_cache(user)

        response = Response(
            _payload(user, added=_names(added), already_assigned=_names(already)),
            status=status.HTTP_200_OK,
        )
        response.success_message = 'Roles assigned successfully.'
        return response

    @transaction.atomic
    def put(self, request):
        user, roles = self._validated(request, ReplaceRolesSerializer)

        held = set(UserRole.objects.filter(user=user).values_list('role_id', flat=True))
        wanted = {role.pk: role for role in roles}

        added = [role for pk, role in wanted.items() if pk not in held]
        unchanged = [role for pk, role in wanted.items() if pk in held]
        removed_qs = UserRole.objects.filter(user=user).exclude(role_id__in=wanted)
        removed = sorted(removed_qs.values_list('role__name', flat=True))

        removed_qs.delete()
        UserRole.objects.bulk_create(
            [UserRole(user=user, role=role) for role in added],
            ignore_conflicts=True,
        )
        clear_permission_cache(user)

        response = Response(
            _payload(
                user,
                added=_names(added),
                removed=removed,
                unchanged=_names(unchanged),
            ),
            status=status.HTTP_200_OK,
        )
        response.success_message = 'User roles replaced successfully.'
        return response

    @transaction.atomic
    def delete(self, request):
        user, roles = self._validated(request, AssignRoleSerializer)

        held = set(UserRole.objects.filter(user=user).values_list('role_id', flat=True))
        removed = [role for role in roles if role.pk in held]
        not_assigned = [role for role in roles if role.pk not in held]

        UserRole.objects.filter(user=user, role_id__in=[role.pk for role in removed]).delete()
        clear_permission_cache(user)

        response = Response(
            _payload(user, removed=_names(removed), not_assigned=_names(not_assigned)),
            status=status.HTTP_200_OK,
        )
        response.success_message = 'Roles removed successfully.'
        return response
