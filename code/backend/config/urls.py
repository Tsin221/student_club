from django.urls import path

from users import views as user_views


urlpatterns = [
    path("api/auth/csrf", user_views.csrf),
    path("api/auth/register", user_views.register),
    path("api/auth/login", user_views.login_view),
    path("api/me/profile", user_views.profile),
]
