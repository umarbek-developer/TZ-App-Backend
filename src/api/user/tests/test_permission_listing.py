import pytest

from apps.rbac.models import Permission, Role, RolePermission

URL = '/api/v1/permissions/'

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalogue(db):
    """A small stand-in for the seeded catalogue."""
    made = {}
    for code, name, description in [
        ('user.view', 'View users', 'List and retrieve user accounts.'),
        ('user.update', 'Update users', 'Modify user accounts.'),
        ('user.delete', 'Delete users', 'Deactivate user accounts.'),
        ('mock.view', 'View mock objects', 'Read the mock business endpoints.'),
    ]:
        made[code], _ = Permission.objects.get_or_create(
            code=code, defaults={'name': name, 'description': description}
        )
    return made


def codes(response):
    return [p['code'] for p in response.data['data']['results']]


# --- filtering ---------------------------------------------------------------


def test_filter_by_exact_code(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'code': 'mock.view'})) == ['mock.view']


def test_filter_by_code_is_case_insensitive(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'code': 'MOCK.VIEW'})) == ['mock.view']


def test_filter_by_exact_code_does_not_match_a_prefix(admin_client, catalogue):
    """?code= is exact — unlike ?search=, which would match all three user.* codes."""
    assert codes(admin_client.get(URL, {'code': 'user'})) == []


def test_filter_by_code_contains(admin_client, catalogue):
    result = set(codes(admin_client.get(URL, {'code_contains': 'view'})))

    # A superset check, not equality: the admin fixture's own role.view /
    # permission.view rows legitimately contain "view" too.
    assert {'user.view', 'mock.view'} <= result
    assert 'user.update' not in result
    assert 'user.delete' not in result


def test_filter_by_namespace(admin_client, catalogue):
    assert set(codes(admin_client.get(URL, {'namespace': 'user'}))) == {
        'user.view',
        'user.update',
        'user.delete',
    }


def test_filter_by_namespace_tolerates_a_trailing_dot(admin_client, catalogue):
    assert set(codes(admin_client.get(URL, {'namespace': 'user.'}))) == {
        'user.view',
        'user.update',
        'user.delete',
    }


def test_filter_by_namespace_does_not_match_a_bare_prefix(admin_client, catalogue):
    """"user" must not also sweep in a hypothetical "username.*" namespace."""
    Permission.objects.create(code='username.view', name='View usernames')

    assert 'username.view' not in codes(admin_client.get(URL, {'namespace': 'user'}))


def test_filter_by_name(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'name': 'mock'})) == ['mock.view']


def test_filter_by_role_id(admin_client, catalogue):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=catalogue['mock.view'])
    RolePermission.objects.create(role=role, permission=catalogue['user.view'])

    assert set(codes(admin_client.get(URL, {'role': str(role.pk)}))) == {
        'mock.view',
        'user.view',
    }


def test_filter_by_role_name(admin_client, catalogue):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=catalogue['mock.view'])

    assert codes(admin_client.get(URL, {'role_name': 'manager'})) == ['mock.view']


def test_filter_by_unknown_role_id_is_400(admin_client, catalogue):
    response = admin_client.get(URL, {'role': '11111111-1111-1111-1111-111111111111'})

    assert response.status_code == 400


def test_filter_unassigned_true(admin_client, catalogue):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=catalogue['mock.view'])

    result = codes(admin_client.get(URL, {'unassigned': 'true'}))

    assert 'mock.view' not in result
    assert 'user.view' in result


def test_filter_unassigned_false(admin_client, catalogue):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=catalogue['mock.view'])

    result = codes(admin_client.get(URL, {'unassigned': 'false'}))

    assert 'mock.view' in result
    assert 'user.view' not in result


def test_unassigned_false_does_not_duplicate_multi_role_permissions(admin_client, catalogue):
    for name in ('Manager', 'Employee'):
        RolePermission.objects.create(
            role=Role.objects.create(name=name), permission=catalogue['mock.view']
        )

    result = codes(admin_client.get(URL, {'unassigned': 'false'}))

    # Without distinct() the join would return mock.view once per granting role.
    assert result.count('mock.view') == 1


def test_filter_by_created_after(admin_client, catalogue):
    permission = Permission.objects.get(code='mock.view')

    stamp = permission.created_at.isoformat()
    response = admin_client.get(URL, {'created_after': stamp})

    assert 'mock.view' in codes(response)


def test_filter_by_created_before_excludes_later_rows(admin_client, catalogue):
    first = Permission.objects.get(code='user.view')
    later = Permission.objects.create(code='zz.later', name='Later')

    response = admin_client.get(URL, {'created_before': first.created_at.isoformat()})

    assert 'zz.later' not in codes(response)
    assert later.created_at > first.created_at


def test_filters_combine(admin_client, catalogue):
    role = Role.objects.create(name='Manager')
    RolePermission.objects.create(role=role, permission=catalogue['user.view'])
    RolePermission.objects.create(role=role, permission=catalogue['mock.view'])

    assert codes(admin_client.get(URL, {'role_name': 'Manager', 'namespace': 'user'})) == [
        'user.view'
    ]


def test_an_unknown_query_param_is_ignored(admin_client, catalogue):
    response = admin_client.get(URL, {'nonsense': 'x'})

    assert response.status_code == 200
    assert response.data['data']['count'] == Permission.objects.count()


# --- searching ---------------------------------------------------------------


def test_search_matches_the_code(admin_client, catalogue):
    assert set(codes(admin_client.get(URL, {'search': 'user.'}))) == {
        'user.view',
        'user.update',
        'user.delete',
    }


def test_search_matches_the_name(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'search': 'View mock'})) == ['mock.view']


def test_search_matches_the_description(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'search': 'Deactivate'})) == ['user.delete']


def test_search_is_case_insensitive(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'search': 'MOCK'})) == ['mock.view']


def test_search_with_no_match_returns_an_empty_page(admin_client, catalogue):
    response = admin_client.get(URL, {'search': 'nothing-matches-this'})

    assert response.status_code == 200
    assert response.data['data']['count'] == 0


def test_search_and_filter_combine(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'namespace': 'user', 'search': 'Deactivate'})) == [
        'user.delete'
    ]


# --- ordering ----------------------------------------------------------------


def test_default_ordering_is_by_code(admin_client, catalogue):
    result = codes(admin_client.get(URL))

    assert result == sorted(result)


def test_ordering_by_code_descending(admin_client, catalogue):
    result = codes(admin_client.get(URL, {'ordering': '-code'}))

    assert result == sorted(result, reverse=True)


def test_ordering_by_name(admin_client, catalogue):
    # Scoped to one namespace so the comparison stays meaningful: PostgreSQL's
    # en_US.UTF-8 collation orders case-insensitively, so mixing the fixture's
    # lowercase names in would not match Python's case-sensitive sorted().
    response = admin_client.get(URL, {'ordering': 'name', 'namespace': 'user'})

    names = [p['name'] for p in response.data['data']['results']]
    assert names == ['Delete users', 'Update users', 'View users']


def test_ordering_by_created_at(admin_client, catalogue):
    response = admin_client.get(URL, {'ordering': 'created_at'})

    stamps = [p['created_at'] for p in response.data['data']['results']]
    assert stamps == sorted(stamps)


def test_ordering_by_an_undeclared_field_is_ignored(admin_client, catalogue):
    response = admin_client.get(URL, {'ordering': 'description'})

    assert response.status_code == 200


def test_ordering_and_filter_combine(admin_client, catalogue):
    assert codes(admin_client.get(URL, {'namespace': 'user', 'ordering': '-code'})) == [
        'user.view',
        'user.update',
        'user.delete',
    ]


# --- pagination --------------------------------------------------------------


def test_list_is_paginated(admin_client, catalogue):
    response = admin_client.get(URL)

    assert set(response.data['data']) >= {'count', 'pages', 'results'}
    assert response.data['data']['count'] == Permission.objects.count()


def test_page_size_limits_the_results(admin_client, catalogue):
    response = admin_client.get(URL, {'page_size': 2})

    assert len(response.data['data']['results']) == 2
    assert response.data['data']['count'] == Permission.objects.count()


def test_pagination_counts_only_filtered_rows(admin_client, catalogue):
    response = admin_client.get(URL, {'namespace': 'user'})

    assert response.data['data']['count'] == 3


# --- query efficiency --------------------------------------------------------


def test_listing_does_not_scale_queries_with_row_count(
    admin_client, catalogue, django_assert_max_num_queries
):
    role = Role.objects.create(name='Manager')
    for permission in catalogue.values():
        RolePermission.objects.create(role=role, permission=permission)

    with django_assert_max_num_queries(5):
        assert admin_client.get(URL).status_code == 200
