import django_filters

from apps.rbac.models import Permission, Role


class PermissionFilter(django_filters.FilterSet):
    """Filters for the permission catalogue.

    Distinct from `?search=`, which is a loose match across several columns. These
    are precise: exact codes, a namespace, or the roles a permission is attached to.
    """

    code = django_filters.CharFilter(
        lookup_expr='iexact',
        help_text='Exact code, case-insensitive. e.g. mock.view',
    )
    code_contains = django_filters.CharFilter(
        field_name='code',
        lookup_expr='icontains',
        help_text='Substring of the code. e.g. view',
    )
    namespace = django_filters.CharFilter(
        method='filter_namespace',
        help_text='Everything under a dotted prefix. e.g. user -> user.view, user.update, ...',
    )
    name = django_filters.CharFilter(
        lookup_expr='icontains',
        help_text='Substring of the human-readable name.',
    )
    role = django_filters.ModelChoiceFilter(
        field_name='roles',
        queryset=Role.objects.all(),
        help_text='Permissions granted to this role id.',
    )
    role_name = django_filters.CharFilter(
        field_name='roles__name',
        lookup_expr='iexact',
        help_text='Permissions granted to this role name. e.g. Manager',
    )
    unassigned = django_filters.BooleanFilter(
        method='filter_unassigned',
        help_text='true -> permissions no role grants; false -> those at least one role grants.',
    )
    created_after = django_filters.IsoDateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='ISO-8601 timestamp.',
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='ISO-8601 timestamp.',
    )

    class Meta:
        model = Permission
        fields = [
            'code',
            'code_contains',
            'namespace',
            'name',
            'role',
            'role_name',
            'unassigned',
            'created_after',
            'created_before',
        ]

    def filter_namespace(self, queryset, name, value):
        value = value.strip().rstrip('.')
        if not value:
            return queryset
        # The trailing dot keeps "user" from also matching a "username.*" namespace.
        return queryset.filter(code__istartswith=f'{value}.')

    def filter_unassigned(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.filter(roles__isnull=True)
        # distinct(): a permission held by several roles would otherwise repeat.
        return queryset.filter(roles__isnull=False).distinct()
