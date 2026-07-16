from django.urls import path

from api.auth.views.login_views import LoginView
from api.auth.views.logout_views import LogoutView
from api.auth.views.profile_views import ProfileView
from api.auth.views.register_views import RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/profile/", ProfileView.as_view(), name="auth-profile"),
]
