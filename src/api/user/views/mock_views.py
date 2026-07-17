"""Mock business resources.

Static JSON stand-ins for real business objects, used to demonstrate that RBAC
gates ordinary endpoints. Deliberately backed by no database tables and no models:
the payloads below are the whole story.

Every endpoint requires `mock.view`, which the seed grants to Admin, Manager and
Employee — so these are the endpoints a non-administrator can actually reach.
"""

from copy import deepcopy

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.permissions import require_permissions

CanViewMock = require_permissions('mock.view')

_UNAUTHORIZED = OpenApiResponse(description='No or invalid token.')
_FORBIDDEN = OpenApiResponse(
    description='Authenticated, but the `mock.view` permission is missing.'
)


# --- payloads ----------------------------------------------------------------
# projects and orders are verbatim from the assignment; employees and documents
# follow the same flat, obviously-fake shape.

PROJECTS = [
    {'id': 1, 'name': 'CRM'},
    {'id': 2, 'name': 'ERP'},
]

ORDERS = [
    {'id': 100, 'price': 500},
]

EMPLOYEES = [
    {'id': 1, 'first_name': 'Aziz', 'last_name': 'Karimov', 'position': 'Backend Developer'},
    {'id': 2, 'first_name': 'Dilnoza', 'last_name': 'Rahimova', 'position': 'Product Manager'},
    {'id': 3, 'first_name': 'Bekzod', 'last_name': 'Tursunov', 'position': 'QA Engineer'},
]

DOCUMENTS = [
    {'id': 1, 'title': 'Service Agreement', 'type': 'contract'},
    {'id': 2, 'title': 'Q1 Financial Report', 'type': 'report'},
    {'id': 3, 'title': 'Vendor Invoice #4417', 'type': 'invoice'},
]


# --- response shapes (documentation only) ------------------------------------


class ProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    price = serializers.IntegerField()


class EmployeeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    position = serializers.CharField()


class DocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    type = serializers.CharField()


# --- views -------------------------------------------------------------------


class StaticMockView(APIView):
    """Returns `payload` to anyone holding `mock.view`.

    The payload is a bare array; it arrives at the client under the standard
    envelope's `data` key, like every other endpoint's body.
    """

    permission_classes = [CanViewMock]
    payload = []
    success_message = 'Retrieved successfully.'

    def get(self, request):
        # deepcopy, not the constant itself: the payload lives for the life of the
        # process, so anything that mutated response.data — a renderer, middleware,
        # a test — would corrupt it for every later request.
        response = Response(deepcopy(self.payload), status=status.HTTP_200_OK)
        response.success_message = self.success_message
        return response


@extend_schema(
    tags=['mock'],
    summary='List mock projects',
    description='Static data. Requires the `mock.view` permission.',
    responses={200: ProjectSerializer(many=True), 401: _UNAUTHORIZED, 403: _FORBIDDEN},
)
class MockProjectsView(StaticMockView):
    payload = PROJECTS
    success_message = 'Projects retrieved successfully.'


@extend_schema(
    tags=['mock'],
    summary='List mock orders',
    description='Static data. Requires the `mock.view` permission.',
    responses={200: OrderSerializer(many=True), 401: _UNAUTHORIZED, 403: _FORBIDDEN},
)
class MockOrdersView(StaticMockView):
    payload = ORDERS
    success_message = 'Orders retrieved successfully.'


@extend_schema(
    tags=['mock'],
    summary='List mock employees',
    description='Static data. Requires the `mock.view` permission.',
    responses={200: EmployeeSerializer(many=True), 401: _UNAUTHORIZED, 403: _FORBIDDEN},
)
class MockEmployeesView(StaticMockView):
    payload = EMPLOYEES
    success_message = 'Employees retrieved successfully.'


@extend_schema(
    tags=['mock'],
    summary='List mock documents',
    description='Static data. Requires the `mock.view` permission.',
    responses={200: DocumentSerializer(many=True), 401: _UNAUTHORIZED, 403: _FORBIDDEN},
)
class MockDocumentsView(StaticMockView):
    payload = DOCUMENTS
    success_message = 'Documents retrieved successfully.'
