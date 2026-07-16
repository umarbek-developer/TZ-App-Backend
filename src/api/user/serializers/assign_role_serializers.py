from rest_framework import serializers

from apps.rbac.models import Role
from apps.users.models import User


class UserBriefSerializer(serializers.ModelSerializer):
    """Just enough of the user to identify them in an assignment response."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'is_active']


class AssignRoleSerializer(serializers.Serializer):
    """Request body for every assign-role operation.

    `user` and `roles` are PrimaryKeyRelatedFields, so a non-existent id is a 400
    with a field-scoped message rather than a 404 or a crash.
    """

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        help_text='UUID of the user.',
    )
    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        many=True,
        allow_empty=False,
        help_text='UUIDs of the roles.',
    )

    def validate_roles(self, value):
        # A payload repeating the same role is a client bug. Silently collapsing it
        # would hide that, and the response counts ("added": [...]) would not add up.
        ids = [role.pk for role in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Duplicate role ids in the request.')
        return value


class ReplaceRolesSerializer(AssignRoleSerializer):
    """Replacement allows an empty list — that is how you strip every role."""

    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        many=True,
        allow_empty=True,
        help_text='UUIDs of the roles. An empty list removes every role.',
    )


# --- response shapes (documentation + a single place defining the payload) ----


class _BaseResponseSerializer(serializers.Serializer):
    user = UserBriefSerializer()
    roles = serializers.ListField(
        child=serializers.CharField(),
        help_text='The role names the user holds after the operation.',
    )


class AssignRoleResponseSerializer(_BaseResponseSerializer):
    added = serializers.ListField(child=serializers.CharField())
    already_assigned = serializers.ListField(child=serializers.CharField())


class ReplaceRolesResponseSerializer(_BaseResponseSerializer):
    added = serializers.ListField(child=serializers.CharField())
    removed = serializers.ListField(child=serializers.CharField())
    unchanged = serializers.ListField(child=serializers.CharField())


class RemoveRolesResponseSerializer(_BaseResponseSerializer):
    removed = serializers.ListField(child=serializers.CharField())
    not_assigned = serializers.ListField(child=serializers.CharField())
