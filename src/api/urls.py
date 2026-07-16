from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # API documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('admin/', include('api.admin.urls')),

    # Both are mounted at the root so the URLs match the spec (/api/v1/auth/...,
    # /api/v1/roles/...). Their patterns do not overlap.
    path('', include('api.user.urls')),
    path('', include('api.auth.urls')),
]
