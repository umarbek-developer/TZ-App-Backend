from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.user.views.assign_permission_views import AssignPermissionView
from api.user.views.assign_role_views import AssignRoleView
from api.user.views.permission_views import PermissionViewSet
from api.user.views.role_views import RoleViewSet

router = DefaultRouter()
router.include_root_view = False
router.register('roles', RoleViewSet, basename='role')
router.register('permissions', PermissionViewSet, basename='permission')

urlpatterns = [
    path('assign-role/', AssignRoleView.as_view(), name='assign-role'),
    path('assign-permission/', AssignPermissionView.as_view(), name='assign-permission'),
    path('', include(router.urls)),
]
