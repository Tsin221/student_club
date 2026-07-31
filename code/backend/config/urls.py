from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from clubs import views as club_views
from users import views as user_views


urlpatterns = [
    #用户注册
    path("api/auth/register", user_views.register),
    #用户登录
    path("api/auth/login", user_views.login_view),
    #查看或修改个人资料
    path("api/me/profile", user_views.profile),
    #我的社团成员关系
    path("api/me/memberships", club_views.my_memberships),
    #管理员查看学生用户列表
    path("api/admin/users", user_views.admin_list_users),
    #管理员重置学生密码
    path(
        "api/admin/users/<int:user_id>/reset-password",
        user_views.admin_reset_password,
    ),
    #管理员社团管理
    path("api/admin/clubs", club_views.admin_clubs),
    path("api/admin/clubs/<int:club_id>", club_views.admin_club_detail),
    path(
        "api/admin/clubs/<int:club_id>/cancel",
        club_views.admin_cancel_club,
    ),
    path(
        "api/admin/clubs/<int:club_id>/leaders",
        club_views.admin_add_leader,
    ),
    path(
        "api/admin/clubs/<int:club_id>/leaders/<int:membership_id>",
        club_views.admin_remove_leader,
    ),
    #管理员成员关系
    path("api/admin/memberships", club_views.admin_list_memberships),
    #负责人社团管理
    path("api/leader/clubs/<int:club_id>", club_views.leader_club_detail),
    path(
        "api/leader/clubs/<int:club_id>/members",
        club_views.leader_list_members,
    ),
    #公开社团列表
    path("api/clubs", club_views.public_list_clubs),
    #社团详情
    path("api/clubs/<int:club_id>", club_views.club_detail),
    #公开招新列表
    path(
        "api/clubs/<int:club_id>/recruitments",
        club_views.public_list_recruitments,
    ),
    #负责人招新管理
    path(
        "api/leader/clubs/<int:club_id>/recruitments",
        club_views.leader_recruitments,
    ),
    path(
        "api/leader/recruitments/<int:recruitment_id>",
        club_views.leader_recruitment_detail,
    ),
    path(
        "api/leader/recruitments/<int:recruitment_id>/end",
        club_views.leader_end_recruitment,
    ),
    #管理员招新记录
    path("api/admin/recruitments", club_views.admin_list_recruitments),
]

#开发环境媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
