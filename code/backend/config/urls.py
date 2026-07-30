from django.urls import path

from users import views as user_views


urlpatterns = [
    #获取 CSRF 令牌
    path("api/auth/csrf", user_views.csrf),
    #用户注册
    path("api/auth/register", user_views.register),
    #用户登录
    path("api/auth/login", user_views.login_view),
    #查看或修改个人资料
    path("api/me/profile", user_views.profile),
]
