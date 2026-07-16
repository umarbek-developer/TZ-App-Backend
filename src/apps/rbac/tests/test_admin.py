import pytest
from django.contrib import admin

from apps.rbac.models import Permission, Role, RolePermission, UserRole

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('model', [Role, Permission, UserRole, RolePermission])
def test_model_is_registered_in_admin(model):
    assert model in admin.site._registry


@pytest.mark.parametrize('model', [Role, Permission, UserRole, RolePermission])
def test_admin_configuration_is_valid(model):
    """admin.checks catches things like autocomplete_fields pointing at a
    ModelAdmin without search_fields — a mistake that only surfaces at runtime."""
    model_admin = admin.site._registry[model]

    assert model_admin.check() == []
