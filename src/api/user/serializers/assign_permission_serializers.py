from rest_framework import serializers

from apps.rbac.models import Permission, Role


class RoleBriefSerializer(serializers.ModelSerializer):
    """Just enough of the role to identify it in an assignment response."""

    class Meta:
        model = Role
        fields = ['id', 'name']


class AssignPermissionSerializer(serializers.Serializer):
    """Request body for every assign-permission operation.

    `role` and `permissions` are PrimaryKeyRelatedFields, so a non-existent id is a
    400 with a field-scoped message rather than a 404 or a crash.
    """

    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        help_text='UUID of the role.',
    )
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        allow_empty=False,
        help_text='UUIDs of the permissions.',
    )

    def validate_permissions(self, value):
        # A payload repeating the same permission is a client bug. Collapsing it
        # silently would hide that, and the response counts would not add up.
        ids = [permission.pk for permission in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Duplicate permission ids in the request.')
        return value


class ReplacePermissionsSerializer(AssignPermissionSerializer):
    """Replacement allows an empty list — that is how you strip every permission."""

    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        allow_empty=True,
        help_text='UUIDs of the permissions. An empty list removes every permission.',
    )


# --- response shapes (documentation + a single place defining the payload) ----


class _BaseResponseSerializer(serializers.Serializer):
    role = RoleBriefSerializer()
    permissions = serializers.ListField(
        child=serializers.CharField(),
        help_text='The permission codes the role carries after the operation.',
    )


class AssignPermissionResponseSerializer(_BaseResponseSerializer):
    added = serializers.ListField(child=serializers.CharField())
    already_assigned = serializers.ListField(child=serializers.CharField())


class ReplacePermissionsResponseSerializer(_BaseResponseSerializer):
    added = serializers.ListField(child=serializers.CharField())
    removed = serializers.ListField(child=serializers.CharField())
    unchanged = serializers.ListField(child=serializers.CharField())


class RemovePermissionsResponseSerializer(_BaseResponseSerializer):
    removed = serializers.ListField(child=serializers.CharField())
    not_assigned = serializers.ListField(child=serializers.CharField())
