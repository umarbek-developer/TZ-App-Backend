from django.core.management.base import BaseCommand
from django.db import transaction

from apps.rbac.models import Permission, Role, RolePermission

# The declared catalogue. This module is the source of truth for it: re-running the
# command reconciles the database back to what is written here.

PERMISSIONS = [
    # (code, name, description)
    ('user.view', 'View users', 'List and retrieve user accounts.'),
    ('user.update', 'Update users', 'Modify user accounts.'),
    ('user.delete', 'Delete users', 'Deactivate user accounts.'),
    ('role.view', 'View roles', 'List and retrieve roles.'),
    ('role.manage', 'Manage roles', 'Create, update and delete roles, and assign them to users.'),
    ('permission.view', 'View permissions', 'List and retrieve permissions.'),
    (
        'permission.manage',
        'Manage permissions',
        'Create, update and delete permissions, and assign them to roles.',
    ),
    ('mock.view', 'View mock objects', 'Read the mock business endpoints.'),
]

ROLES = [
    # (name, description)
    ('Admin', 'Full access to every permission.'),
    ('Manager', 'Reads user records and mock business data.'),
    ('Employee', 'Reads mock business data.'),
    ('Guest', 'Holds no permissions.'),
]

ALL_PERMISSION_CODES = [code for code, _, _ in PERMISSIONS]

ROLE_PERMISSIONS = {
    'Admin': ALL_PERMISSION_CODES,
    'Manager': ['mock.view', 'user.view'],
    'Employee': ['mock.view'],
    'Guest': [],
}


class Command(BaseCommand):
    help = (
        'Seed the RBAC roles, permissions and their grants. Safe to run repeatedly: '
        'existing rows are reused and never duplicated.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune',
            action='store_true',
            help=(
                'Also revoke role permissions that are not in the declared catalogue. '
                'Off by default so the command never destroys grants made by hand.'
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        prune = options['prune']

        permissions = self._seed_permissions()
        roles = self._seed_roles()
        self._seed_grants(roles, permissions, prune=prune)

        self.stdout.write(self.style.SUCCESS('\nSeeding complete.'))
        self._summarise(roles)

    # -- steps ---------------------------------------------------------------

    def _seed_permissions(self):
        self.stdout.write('Permissions:')
        permissions = {}
        for code, name, description in PERMISSIONS:
            # update_or_create, not get_or_create: the catalogue above is the source
            # of truth, so a renamed permission propagates on the next run instead of
            # silently keeping the old label.
            permission, created = Permission.objects.update_or_create(
                code=code,
                defaults={'name': name, 'description': description},
            )
            permissions[code] = permission
            self._report(code, created)
        return permissions

    def _seed_roles(self):
        self.stdout.write('\nRoles:')
        roles = {}
        for name, description in ROLES:
            role, created = Role.objects.update_or_create(
                name=name,
                defaults={'description': description},
            )
            roles[name] = role
            self._report(name, created)
        return roles

    def _seed_grants(self, roles, permissions, *, prune):
        self.stdout.write('\nGrants:')
        for role_name, codes in ROLE_PERMISSIONS.items():
            role = roles[role_name]

            for code in codes:
                _, created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permissions[code],
                )
                self._report(f'{role_name} -> {code}', created)

            if prune:
                self._prune_grants(role, codes)

    def _prune_grants(self, role, keep_codes):
        extra = RolePermission.objects.filter(role=role).exclude(permission__code__in=keep_codes)
        for grant in extra:
            self.stdout.write(
                self.style.WARNING(f'  revoked  {role.name} -> {grant.permission.code}')
            )
        extra.delete()

    # -- output --------------------------------------------------------------

    def _report(self, label, created):
        if created:
            self.stdout.write(self.style.SUCCESS(f'  created  {label}'))
        else:
            self.stdout.write(f'  exists   {label}')

    def _summarise(self, roles):
        self.stdout.write('\nResulting role permissions:')
        for name in roles:
            codes = sorted(
                RolePermission.objects.filter(role__name=name).values_list(
                    'permission__code', flat=True
                )
            )
            self.stdout.write(f'  {name:<9} {", ".join(codes) if codes else "(none)"}')
