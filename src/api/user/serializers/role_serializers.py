from rest_framework import serializers

from apps.rbac.models import Role


class RoleSerializer(serializers.ModelSerializer):
    """Read/write representation of a role.

    `permissions` is read-only here: grants are managed through the dedicated
    assign-permission endpoint, not by editing a role in place.
    """

    # Declared explicitly rather than letting ModelSerializer attach its own
    # UniqueValidator, so that uniqueness is enforced case-insensitively in one
    # place with one message.
    name = serializers.CharField(max_length=100)

    permissions = serializers.SlugRelatedField(
        slug_field='code',
        many=True,
        read_only=True,
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'permissions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'permissions', 'created_at', 'updated_at']

    def validate_name(self, value):
        value = value.strip()

        # Case-insensitive: "admin" alongside "Admin" would be two distinct rows
        # that read as the same role to anyone using the API.
        duplicates = Role.objects.filter(name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError('A role with this name already exists.')

        return value
