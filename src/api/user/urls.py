from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.user.views.role_views import RoleViewSet

router = DefaultRouter()
router.include_root_view = False
router.register('roles', RoleViewSet, basename='role')

urlpatterns = [
    path('', include(router.urls)),
]
