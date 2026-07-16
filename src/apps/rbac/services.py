"""Database-backed permission lookups.

The chain is `User -> UserRole -> Role -> RolePermission -> Permission.code`, and a
user's effective permissions are the **union** across every role they hold.

Everything here is read-only and safe to call with `None` or an anonymous user.
"""

from apps.rbac.models import Permission, Role

# Resolved codes are memoised on the user instance. DRF asks a permission class at
# least once per request — and again per object for object-level checks — so without
# this a single request would re-run the same join several times. request.user is a
# per-request object, so the cache dies with the request.
PERMISSION_CACHE_ATTR = '_rbac_permission_codes'


def _is_eligible(user):
    """Anonymous, missing, or deactivated users hold nothing.

    The `is_active` check is belt-and-braces: SimpleJWT already rejects tokens
    belonging to inactive users, but these helpers are also callable outside the
    request cycle, where nothing else would enforce it.
    """
    return bool(
        user is not None
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
    )


def get_user_permission_codes(user):
    """Return the user's effective permission codes as a frozenset.

    One query, regardless of how many roles the user holds. Repeat calls for the
    same user instance are free.
    """
    if not _is_eligible(user):
        return frozenset()

    cached = getattr(user, PERMISSION_CACHE_ATTR, None)
    if cached is not None:
        return cached

    codes = frozenset(
        Permission.objects.filter(roles__user_roles__user=user)
        .distinct()
        .values_list('code', flat=True)
    )
    setattr(user, PERMISSION_CACHE_ATTR, codes)
    return codes


def clear_permission_cache(user):
    """Drop the memoised codes.

    Call after changing a user's roles within the same request/instance lifetime,
    otherwise the stale set is reused.
    """
    if hasattr(user, PERMISSION_CACHE_ATTR):
        delattr(user, PERMISSION_CACHE_ATTR)


def user_has_permission(user, code):
    """True when the user holds `code` through any of their roles."""
    return code in get_user_permission_codes(user)


def user_has_all_permissions(user, codes):
    """True when the user holds every one of `codes`. Empty `codes` is True."""
    return get_user_permission_codes(user).issuperset(codes)


def user_has_any_permission(user, codes):
    """True when the user holds at least one of `codes`. Empty `codes` is False."""
    codes = frozenset(codes)
    if not codes:
        return False
    return bool(get_user_permission_codes(user) & codes)


def get_user_roles(user):
    """The user's roles, as a queryset. One query."""
    if not _is_eligible(user):
        return Role.objects.none()
    return Role.objects.filter(user_roles__user=user).distinct()


def get_user_role_names(user):
    """The user's role names as a frozenset. One query."""
    return frozenset(get_user_roles(user).values_list('name', flat=True))
