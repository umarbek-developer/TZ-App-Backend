import pytest

from api.user.views.mock_views import DOCUMENTS, EMPLOYEES

from .conftest import grant, jwt_client_for, make_user

pytestmark = pytest.mark.django_db

PROJECTS_URL = '/api/v1/mock/projects/'
ORDERS_URL = '/api/v1/mock/orders/'
EMPLOYEES_URL = '/api/v1/mock/employees/'
DOCUMENTS_URL = '/api/v1/mock/documents/'

ALL_URLS = [PROJECTS_URL, ORDERS_URL, EMPLOYEES_URL, DOCUMENTS_URL]


# --- anonymous -> 401 --------------------------------------------------------


@pytest.mark.parametrize('url', ALL_URLS)
def test_anonymous_gets_401(api, url):
    assert api.get(url).status_code == 401


# --- authenticated without mock.view -> 403 ----------------------------------


@pytest.mark.parametrize('url', ALL_URLS)
def test_guest_gets_403(guest_client, url):
    """Guest holds a role, but that role carries nothing."""
    assert guest_client.get(url).status_code == 403


@pytest.mark.parametrize('url', ALL_URLS)
def test_role_and_permission_codes_do_not_grant_mock_view(admin_client, url):
    """The RBAC admin codes are unrelated to mock.view — no blanket admin bypass."""
    assert admin_client.get('/api/v1/roles/').status_code == 200
    assert admin_client.get(url).status_code == 403


@pytest.mark.parametrize('url', ALL_URLS)
def test_a_user_with_no_roles_gets_403(url, db):
    client = jwt_client_for(make_user('roleless@test.com'))

    assert client.get(url).status_code == 403


@pytest.mark.parametrize('url', ALL_URLS)
def test_inactive_user_gets_401(url, db):
    """SimpleJWT rejects a deactivated user's token before RBAC is consulted."""
    user = make_user('gone@test.com')
    grant(user, 'TestCrew', 'mock.view')
    client = jwt_client_for(user)
    assert client.get(url).status_code == 200

    user.is_active = False
    user.save(update_fields=['is_active'])

    assert client.get(url).status_code == 401


# --- authenticated with mock.view -> 200 -------------------------------------


@pytest.mark.parametrize('url', ALL_URLS)
def test_employee_gets_200(employee_client, url):
    """The employee fixture's role carries mock.view."""
    assert employee_client.get(url).status_code == 200


# --- payloads ----------------------------------------------------------------


def test_projects_payload_matches_the_specification(employee_client):
    response = employee_client.get(PROJECTS_URL)

    assert response.data['data'] == [{'id': 1, 'name': 'CRM'}, {'id': 2, 'name': 'ERP'}]


def test_orders_payload_matches_the_specification(employee_client):
    response = employee_client.get(ORDERS_URL)

    assert response.data['data'] == [{'id': 100, 'price': 500}]


def test_employees_payload(employee_client):
    response = employee_client.get(EMPLOYEES_URL)

    assert response.data['data'] == EMPLOYEES
    assert len(response.data['data']) == 3


def test_documents_payload(employee_client):
    response = employee_client.get(DOCUMENTS_URL)

    assert response.data['data'] == DOCUMENTS
    assert len(response.data['data']) == 3


@pytest.mark.parametrize(
    'url,keys',
    [
        (PROJECTS_URL, {'id', 'name'}),
        (ORDERS_URL, {'id', 'price'}),
        (EMPLOYEES_URL, {'id', 'first_name', 'last_name', 'position'}),
        (DOCUMENTS_URL, {'id', 'title', 'type'}),
    ],
)
def test_items_match_their_documented_shape(employee_client, url, keys):
    """Guards the payloads against drifting from the serializers Swagger publishes."""
    for item in employee_client.get(url).data['data']:
        assert set(item) == keys


@pytest.mark.parametrize('url', ALL_URLS)
def test_payload_is_a_bare_array_not_a_paginated_page(employee_client, url):
    """The spec shows a plain array. It travels under the response envelope's `data`
    key like every other body, but the project-wide pagination must not page it."""
    data = employee_client.get(url).data['data']

    assert isinstance(data, list)


@pytest.mark.parametrize('url', ALL_URLS)
def test_every_item_has_a_unique_id(employee_client, url):
    ids = [item['id'] for item in employee_client.get(url).data['data']]

    assert len(ids) == len(set(ids))


# --- no database ------------------------------------------------------------


@pytest.mark.parametrize('url', ALL_URLS)
def test_serving_the_payload_costs_no_data_queries(employee_client, url, django_assert_num_queries):
    """Exactly one query: resolving the caller's permissions. Nothing fetches data,
    because there is no table to fetch it from."""
    with django_assert_num_queries(1):
        assert employee_client.get(url).status_code == 200


def test_the_mock_endpoints_have_no_models():
    """'Do NOT create database tables' — assert it rather than trust it."""
    from django.apps import apps

    tables = {model._meta.db_table for model in apps.get_models()}

    assert not any('mock' in table for table in tables)


@pytest.mark.parametrize('url', ALL_URLS)
def test_payload_is_not_mutated_between_requests(employee_client, url):
    """The views hand out a module-level list; a caller must not be able to alter it."""
    first = employee_client.get(url).data['data']
    first.append({'id': 999})

    second = employee_client.get(url).data['data']

    assert not any(item.get('id') == 999 for item in second)


# --- writes are not offered --------------------------------------------------


@pytest.mark.parametrize('url', ALL_URLS)
def test_post_is_not_allowed(employee_client, url):
    assert employee_client.post(url, {}, format='json').status_code == 405
