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
    # ── S07：入社申请与通知 ──
    #学生提交入社申请
    path(
        "api/recruitments/<int:recruitment_id>/applications",
        club_views.student_create_application,
    ),
    #学生查看本人全部申请
    path("api/me/join-applications", club_views.my_join_applications),
    #负责人查看本社团申请
    path(
        "api/leader/clubs/<int:club_id>/join-applications",
        club_views.leader_join_applications,
    ),
    #负责人通过申请
    path(
        "api/leader/join-applications/<int:application_id>/approve",
        club_views.leader_approve_application,
    ),
    #负责人拒绝申请
    path(
        "api/leader/join-applications/<int:application_id>/reject",
        club_views.leader_reject_application,
    ),
    #管理员查看全量申请
    path(
        "api/admin/join-applications",
        club_views.admin_join_applications,
    ),
    #学生查看通知
    path("api/me/notifications", club_views.my_notifications),
    # ── S08：成员退出与移除 ──
    #学生主动退出社团
    path(
        "api/me/memberships/<int:membership_id>/exit",
        club_views.student_exit_membership,
    ),
    #负责人移除普通成员
    path(
        "api/leader/memberships/<int:membership_id>/remove",
        club_views.leader_remove_member,
    ),
    # ── S09：社团公告 ──
    #成员查看公告
    path(
        "api/clubs/<int:club_id>/announcements",
        club_views.member_list_announcements,
    ),
    #负责人管理公告（列表+创建）
    path(
        "api/leader/clubs/<int:club_id>/announcements",
        club_views.leader_announcements,
    ),
    #负责人修改或删除公告
    path(
        "api/leader/announcements/<int:announcement_id>",
        club_views.leader_announcement_detail,
    ),
    #管理员查看已注销社团公告历史
    path(
        "api/admin/clubs/<int:club_id>/announcements",
        club_views.admin_list_announcements,
    ),
    # ── S10：帖子发布、列表、详情与置顶 ──
    #成员查看和发布帖子
    path(
        "api/clubs/<int:club_id>/posts",
        club_views.posts_list_or_create,
    ),
    #帖子详情
    path("api/posts/<int:post_id>", club_views.post_detail),
    #负责人置顶/取消置顶帖子
    path(
        "api/leader/posts/<int:post_id>/pin",
        club_views.leader_pin_post,
    ),
    # ── S11：帖子回复 ──
    #成员查看和发布回复
    path(
        "api/posts/<int:post_id>/replies",
        club_views.replies_list_or_create,
    ),
    # ── S12：帖子点赞 ──
    #成员点赞/取消点赞帖子
    path(
        "api/posts/<int:post_id>/like",
        club_views.post_like_create_or_delete,
    ),
    # ── S13：社团评价 ──
    #成员提交评价
    path(
        "api/clubs/<int:club_id>/evaluations",
        club_views.create_evaluation,
    ),
    #学生查看本人全部评价
    path("api/me/evaluations", club_views.my_evaluations),
    #学生修改本人评价
    path(
        "api/me/evaluations/<int:evaluation_id>",
        club_views.update_evaluation,
    ),
    #管理员查看全部评价
    path("api/admin/evaluations", club_views.admin_evaluations),
]

#开发环境媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
