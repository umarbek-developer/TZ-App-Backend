import pytest

from apps.rbac.models import Permission, Role, RolePermission

URL = '/api/v1/roles/'

pytestmark = pytest.mark.django_db


@pytest.fixture
def roles():
    return [
        Role.objects.create(name='Admin', description='Runs everything'),
        Role.objects.create(name='Manager', description='Runs a team'),
        Role.objects.create(name='Employee', description='Does the work'),
        Role.objects.create(name='Guest', description='Reads nothing'),
    ]


# --- pagination --------------------------------------------------------------


def test_list_is_paginated(admin_client, roles):
    response = admin_client.get(URL)

    assert response.status_code == 200
    assert set(response.data) >= {'count', 'pages', 'results'}
    # The admin fixture's own role exists too.
    assert response.data['count'] == Role.objects.count()


def test_page_size_limits_the_results(admin_client, roles):
    response = admin_client.get(URL, {'page_size': 2})

    assert len(response.data['results']) == 2
    assert response.data['count'] == Role.objects.count()


def test_pages_reports_the_page_count(admin_client, roles):
    response = admin_client.get(URL, {'page_size': 2})

    total = Role.objects.count()
    assert response.data['pages'] == -(-total // 2)  # ceil


def test_second_page_returns_different_rows(admin_client, roles):
    first = admin_client.get(URL, {'page_size': 2, 'page': 1}).data['results']
    second = admin_client.get(URL, {'page_size': 2, 'page': 2}).data['results']

    assert {r['id'] for r in first}.isdisjoint({r['id'] for r in second})


def test_paging_past_the_end_is_404(admin_client, roles):
    assert admin_client.get(URL, {'page': 999}).status_code == 404


# --- search ------------------------------------------------------------------


def test_search_matches_the_name(admin_client, roles):
    response = admin_client.get(URL, {'search': 'Manager'})

    assert [r['name'] for r in response.data['results']] == ['Manager']


def test_search_matches_the_description(admin_client, roles):
    response = admin_client.get(URL, {'search': 'Does the work'})

    assert [r['name'] for r in response.data['results']] == ['Employee']


def test_search_is_case_insensitive(admin_client, roles):
    response = admin_client.get(URL, {'search': 'mAnAgEr'})

    assert [r['name'] for r in response.data['results']] == ['Manager']


def test_search_matches_a_partial_term(admin_client, roles):
    response = admin_client.get(URL, {'search': 'Runs'})

    assert {r['name'] for r in response.data['results']} == {'Admin', 'Manager'}


def test_search_with_no_match_returns_an_empty_page(admin_client, roles):
    response = admin_client.get(URL, {'search': 'nothing-matches-this'})

    assert response.status_code == 200
    assert response.data['count'] == 0
    assert response.data['results'] == []


# --- ordering ----------------------------------------------------------------


def test_default_ordering_is_by_name(admin_client, roles):
    names = [r['name'] for r in admin_client.get(URL).data['results']]

    assert names == sorted(names)


def test_ordering_by_name_descending(admin_client, roles):
    names = [r['name'] for r in admin_client.get(URL, {'ordering': '-name'}).data['results']]

    assert names == sorted(names, reverse=True)


def test_ordering_by_created_at(admin_client, roles):
    response = admin_client.get(URL, {'ordering': 'created_at'})

    stamps = [r['created_at'] for r in response.data['results']]
    assert stamps == sorted(stamps)


def test_ordering_by_created_at_descending(admin_client, roles):
    response = admin_client.get(URL, {'ordering': '-created_at'})

    stamps = [r['created_at'] for r in response.data['results']]
    assert stamps == sorted(stamps, reverse=True)


def test_ordering_by_an_undeclared_field_is_ignored(admin_client, roles):
    """description is not in ordering_fields; DRF must fall back, not error."""
    response = admin_client.get(URL, {'ordering': 'description'})

    assert response.status_code == 200


def test_search_and_ordering_combine(admin_client, roles):
    response = admin_client.get(URL, {'search': 'Runs', 'ordering': '-name'})

    assert [r['name'] for r in response.data['results']] == ['Manager', 'Admin']


# --- query efficiency --------------------------------------------------------


def test_listing_does_not_scale_queries_with_row_count(
    admin_client, roles, django_assert_max_num_queries
):
    """Rendering each role's permission codes must not cost a query per row."""
    view, _ = Permission.objects.get_or_create(code='mock.view', defaults={'name': 'View mock'})
    for role in roles:
        RolePermission.objects.create(role=role, permission=view)

    # permissions resolution + count + page + prefetch, and nothing per-row.
    with django_assert_max_num_queries(5):
        response = admin_client.get(URL)

    assert response.status_code == 200
