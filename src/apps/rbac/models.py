import uuid

from django.conf import settings
from django.db import models


class UUIDModel(models.Model):
    """UUID primary key, shared by every model in this app.

    UUIDs are used throughout because apps.users.User already has a UUID pk, and
    mixing integer and UUID identifiers across the same API would be confusing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedUUIDModel(UUIDModel):
    """Adds created/updated stamps. Used by the catalogue models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Role(TimeStampedUUIDModel):
    """A named bundle of permissions, e.g. Admin, Manager, Employee, Guest."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')

    permissions = models.ManyToManyField(
        'rbac.Permission',
        through='rbac.RolePermission',
        related_name='roles',
        blank=True,
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Permission(TimeStampedUUIDModel):
    """A single capability, identified by a dotted code such as `mock.view`.

    Unrelated to django.contrib.auth.Permission — this is our own table, and the
    only permission concept the API will consult.
    """

    code = models.CharField(
        max_length=100,
        unique=True,
        help_text='Dotted capability code checked by the API, e.g. "user.view".',
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.code


class UserRole(UUIDModel):
    """Grants a role to a user. A user may hold several roles."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_roles',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'role'], name='unique_user_role'),
        ]
        ordering = ['user__email', 'role__name']

    def __str__(self):
        return f'{self.user.email} -> {self.role.name}'


class RolePermission(UUIDModel):
    """Grants a permission to a role."""

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions',
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['role', 'permission'], name='unique_role_permission'
            ),
        ]
        ordering = ['role__name', 'permission__code']

    def __str__(self):
        return f'{self.role.name} -> {self.permission.code}'
