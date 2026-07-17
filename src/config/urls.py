from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('api/v1/', include('api.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    # Media only: contrib.staticfiles serves the admin's own assets while DEBUG
    # is on, and this project ships no static files of its own.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
