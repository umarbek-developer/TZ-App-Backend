from django.contrib import admin

from .models import Permission, Role, RolePermission, UserRole


class RolePermissionInline(admin.TabularInline):
    """Edit a role's permissions from the role page itself."""

    model = RolePermission
    extra = 1
    autocomplete_fields = ['permission']


class UserRoleInline(admin.TabularInline):
    """Edit a role's members from the role page itself."""

    model = UserRole
    extra = 1
    autocomplete_fields = ['user']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'permission_count', 'user_count', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('name',)
    inlines = [RolePermissionInline, UserRoleInline]

    def get_queryset(self, request):
        # Without the annotations, the two count columns would fire a query per row.
        return super().get_queryset(request).prefetch_related('role_permissions', 'user_roles')

    @admin.display(description='Permissions')
    def permission_count(self, obj):
        return obj.role_permissions.count()

    @admin.display(description='Users')
    def user_count(self, obj):
        return obj.user_roles.count()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'description', 'created_at')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('code',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'role__name')
    readonly_fields = ('id',)
    autocomplete_fields = ('user', 'role')
    # __str__ touches user.email and role.name; without this the changelist would
    # issue two extra queries per row.
    list_select_related = ('user', 'role')


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission')
    list_filter = ('role',)
    search_fields = ('role__name', 'permission__code', 'permission__name')
    readonly_fields = ('id',)
    autocomplete_fields = ('role', 'permission')
    list_select_related = ('role', 'permission')
