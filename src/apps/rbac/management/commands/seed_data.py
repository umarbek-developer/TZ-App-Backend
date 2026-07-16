from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.rbac.models import Permission, Role, RolePermission, UserRole

User = get_user_model()

# The seeded administrator. Authorisation is purely database-driven — is_superuser
# grants nothing on its own — so this account is useful only because it holds the
# Admin role, which carries every permission.
ADMIN_EMAIL = 'admin@gmail.com'
ADMIN_PASSWORD = 'admin123'
ADMIN_ROLE = 'Admin'

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
        self._seed_admin(roles)

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

    def _seed_admin(self, roles):
        self.stdout.write('\nAdministrator:')
        user = User.objects.filter(email__iexact=ADMIN_EMAIL).first()

        if user is None:
            user = User.objects.create_superuser(
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD,
                first_name='Admin',
                last_name='User',
            )
            self._report(f'{ADMIN_EMAIL} (superuser)', True)
        else:
            # Re-activate a soft-deleted or demoted admin, but never touch the
            # password: re-seeding must not silently reset a changed credential.
            flags = ('is_superuser', 'is_staff', 'is_active')
            repaired = [f for f in flags if not getattr(user, f)]
            for field in repaired:
                setattr(user, field, True)
            if repaired:
                user.save(update_fields=repaired)
                self.stdout.write(
                    self.style.WARNING(f'  repaired {ADMIN_EMAIL} ({", ".join(repaired)})')
                )
            else:
                self._report(f'{ADMIN_EMAIL} (superuser)', False)

        _, created = UserRole.objects.get_or_create(user=user, role=roles[ADMIN_ROLE])
        self._report(f'{ADMIN_EMAIL} -> {ADMIN_ROLE}', created)
        return user

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
        self.stdout.write(f'\nAdministrator login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}')
