from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.user.views.assign_permission_views import AssignPermissionView
from api.user.views.assign_role_views import AssignRoleView
from api.user.views.mock_views import (
    MockDocumentsView,
    MockEmployeesView,
    MockOrdersView,
    MockProjectsView,
)
from api.user.views.permission_views import PermissionViewSet
from api.user.views.role_views import RoleViewSet

router = DefaultRouter()
router.include_root_view = False
router.register('roles', RoleViewSet, basename='role')
router.register('permissions', PermissionViewSet, basename='permission')

urlpatterns = [
    path('assign-role/', AssignRoleView.as_view(), name='assign-role'),
    path('assign-permission/', AssignPermissionView.as_view(), name='assign-permission'),

    path('mock/projects/', MockProjectsView.as_view(), name='mock-projects'),
    path('mock/orders/', MockOrdersView.as_view(), name='mock-orders'),
    path('mock/employees/', MockEmployeesView.as_view(), name='mock-employees'),
    path('mock/documents/', MockDocumentsView.as_view(), name='mock-documents'),

    path('', include(router.urls)),
]
