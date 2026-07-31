from django.urls import path

from users import views as user_views


urlpatterns = [
    #用户注册
    path("api/auth/register", user_views.register),
    #用户登录
    path("api/auth/login", user_views.login_view),
    #查看或修改个人资料
    path("api/me/profile", user_views.profile),
    #管理员查看学生用户列表
    path("api/admin/users", user_views.admin_list_users),
    #管理员重置学生密码
    path(
        "api/admin/users/<int:user_id>/reset-password",
        user_views.admin_reset_password,
    ),
]
