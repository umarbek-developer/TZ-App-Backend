import re

from rest_framework import serializers

from apps.rbac.models import Permission

# Codes are compared by exact string match at every permission check, so a code
# stored as "Mock.View" or "mock view" could never match anything the API asks for.
# Constrain the shape rather than letting such a row exist.
CODE_PATTERN = re.compile(r'^[a-z0-9]+(?:[._-][a-z0-9]+)*$')


class PermissionSerializer(serializers.ModelSerializer):
    """Read/write representation of a permission.

    `roles` is read-only: which roles hold a permission is managed through the
    assign-permission endpoint, not by editing the permission itself.
    """

    # Declared explicitly to drop ModelSerializer's own UniqueValidator, so
    # uniqueness is enforced case-insensitively in one place with one message.
    code = serializers.CharField(
        max_length=100,
        help_text='Dotted capability code, lowercase. e.g. mock.view',
    )

    roles = serializers.SlugRelatedField(slug_field='name', many=True, read_only=True)

    class Meta:
        model = Permission
        fields = ['id', 'code', 'name', 'description', 'roles', 'created_at', 'updated_at']
        read_only_fields = ['id', 'roles', 'created_at', 'updated_at']

    def validate_code(self, value):
        # Lowercased rather than rejected on case: "Mock.View" is plainly meant to be
        # mock.view, and storing both would create two codes that read alike but
        # behave differently.
        value = value.strip().lower()

        if not CODE_PATTERN.match(value):
            raise serializers.ValidationError(
                'Codes must be lowercase words joined by "." , "_" or "-", '
                f'e.g. "mock.view". Got "{value}".'
            )

        duplicates = Permission.objects.filter(code__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError('A permission with this code already exists.')

        return value

    def validate_name(self, value):
        return value.strip()
