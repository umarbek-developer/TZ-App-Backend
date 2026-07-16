from django.db import models

from apps.users.models import User


class BaseModel(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_created_by',
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_updated_by',
        null=True,
        blank=True,
    )
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        # Was '%(class)s_updated_by', colliding with updated_by above. The clash is
        # dormant only because nothing inherits BaseModel yet; the first concrete
        # subclass would fail system checks (fields.E304/E305) and refuse to start.
        related_name='%(class)s_deleted_by',
        null=True,
        blank=True,
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
