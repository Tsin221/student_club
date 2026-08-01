"""S15 内容举报 — 后端测试。"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/auth/login"


# ── 工具函数 ──────────────────────────────────────────────────

def response_body(response):
    return json.loads(response.content)


def create_student(**overrides):
    data = {
        "username": "test_student",
        "password": "StrongPass!2026",
        "name": "测试学生",
        "phone": "13800001111",
        "major_class": "计算机1班",
        "grade": "2026",
        **overrides,
    }
    return get_user_model().objects.create_user(**data)


def create_admin(username="admin_test", password="AdminPass!2026"):
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        name="系统管理员",
        phone="",
        major_class="",
        grade="",
        platform_role=get_user_model().PlatformRole.ADMIN,
        account_status=get_user_model().AccountStatus.ACTIVE,
    )


def login(client, username, password):
    return client.post(
        LOGIN_URL,
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login_as_student(username="test_student"):
    student = create_student(username=username)
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    assert resp.status_code == 200
    return client, student


def create_test_club(name="测试社团", category="学术科技", introduction="简介", logo="logos/test.png"):
    from clubs.models import Club

    return Club.objects.create(
        name=name,
        category=category,
        introduction=introduction,
        logo=logo,
    )


def create_test_membership(user, club, member_status="active", club_role="member"):
    from clubs.models import ClubMembership

    return ClubMembership.objects.create(
        user=user,
        club=club,
        member_status=member_status,
        club_role=club_role,
    )


def create_test_post(club, author, title="测试帖子", content="测试内容"):
    from clubs.models import Post

    return Post.objects.create(
        club=club,
        author=author,
        title=title,
        content=content,
    )


def create_test_reply(post, author, content="测试回复"):
    from clubs.models import Reply

    return Reply.objects.create(
        post=post,
        author=author,
        content=content,
    )


def create_test_report(reporter, post=None, reply=None, reason="测试举报", status="待处理"):
    from clubs.models import ContentReport

    return ContentReport.objects.create(
        reporter=reporter,
        post=post,
        reply=reply,
        reason=reason,
        status=status,
    )


def setup_member_and_club():
    """创建学生、社团、成员关系的快捷函数。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club)
    return client, student, club, membership


def setup_leader_and_club():
    """创建负责人、社团的快捷函数。"""
    client, student = login_as_student(username="test_leader")
    club = create_test_club()
    create_test_membership(student, club, club_role="leader")
    return client, student, club


def setup_member_club_and_post():
    """创建成员、社团、帖子的快捷函数。"""
    client, student, club, membership = setup_member_and_club()
    post = create_test_post(club, student)
    return client, student, club, post


def setup_member_club_post_and_reply():
    """创建成员、社团、帖子、回复的快捷函数。"""
    client, student, club, post = setup_member_club_and_post()
    reply = create_test_reply(post, student)
    return client, student, club, post, reply


# ═══════════════════════════════════════════════════════════════
# POST /api/posts/{post_id}/reports — 举报帖子
# ═══════════════════════════════════════════════════════════════


def test_report_post_success():
    """在社成员可以成功举报正常帖子。"""
    client, _student, _club, post = setup_member_club_and_post()

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["reason"] == "内容不当"
    assert body["data"]["post_id"] == post.id
    assert body["data"]["reply_id"] is None
    assert body["data"]["status"] == "待处理"


def test_report_post_missing_reason():
    """举报缺少 reason 时返回错误。"""
    client, _student, _club, post = setup_member_club_and_post()

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_report_post_empty_reason():
    """举报原因为空白时返回错误。"""
    client, _student, _club, post = setup_member_club_and_post()

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "   "}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_report_post_deleted():
    """已删除帖子不能举报。"""
    client, _student, _club, post = setup_member_club_and_post()
    post.status = "已删除"
    post.save()

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "POST_DELETED"


def test_report_post_non_member():
    """非成员不能举报帖子。"""
    client, _student, _club, post = setup_member_club_and_post()

    # 另一个学生，未加入社团
    other_client, _other = login_as_student(username="other_student")

    resp = other_client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_MEMBER"


def test_report_post_exited_member():
    """已退出成员不能举报帖子。"""
    client, student, club = setup_leader_and_club()  # using leader to create post
    post = create_test_post(club, student)

    # 另一个学生作为成员
    member = create_student(username="member_student")
    create_test_membership(member, club)
    member_client = Client()
    login(member_client, "member_student", "StrongPass!2026")

    # 先退出
    from clubs.models import ClubMembership
    m = ClubMembership.objects.get(user=member, club=club)
    m.member_status = "exited"
    m.save()

    resp = member_client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 403


def test_report_post_cancelled_club():
    """已注销社团帖子不能举报。"""
    client, _student, club, post = setup_member_club_and_post()
    club.status = "cancelled"
    club.save()

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_report_post_unauthenticated():
    """未认证用户不能举报。"""
    client, student, club, post = setup_member_club_and_post()
    # 使用未认证的客户端
    unauth_client = Client()
    resp = unauth_client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 401


def test_report_post_leader_can_report():
    """负责人也可以举报帖子。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    assert response_body(resp)["code"] == "SUCCESS"


def test_report_post_rejects_disallowed_fields():
    """拒绝不允许的字段。"""
    client, _student, _club, post = setup_member_club_and_post()

    resp = client.post(
        f"/api/posts/{post.id}/reports",
        data=json.dumps({"reason": "内容不当", "status": "已采纳"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_report_post_wrong_method():
    """GET 请求返回 405。"""
    client, _student, _club, post = setup_member_club_and_post()

    resp = client.get(f"/api/posts/{post.id}/reports")

    assert resp.status_code == 405


def test_report_post_not_found():
    """不存在的帖子返回 404。"""
    client, _student, _club, _post = setup_member_club_and_post()

    resp = client.post(
        "/api/posts/99999/reports",
        data=json.dumps({"reason": "内容不当"}),
        content_type="application/json",
    )

    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# POST /api/replies/{reply_id}/reports — 举报回复
# ═══════════════════════════════════════════════════════════════


def test_report_reply_success():
    """在社成员可以成功举报正常回复。"""
    client, _student, _club, _post, reply = setup_member_club_post_and_reply()

    resp = client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({"reason": "不当言论"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["reason"] == "不当言论"
    assert body["data"]["post_id"] is None
    assert body["data"]["reply_id"] == reply.id
    assert body["data"]["status"] == "待处理"


def test_report_reply_missing_reason():
    """举报回复缺少 reason 时返回错误。"""
    client, _student, _club, _post, reply = setup_member_club_post_and_reply()

    resp = client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_report_reply_deleted():
    """已删除回复不能举报。"""
    client, _student, _club, _post, reply = setup_member_club_post_and_reply()
    reply.status = "已删除"
    reply.save()

    resp = client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({"reason": "不当言论"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "REPLY_DELETED"


def test_report_reply_post_deleted():
    """父帖已删除时不能举报回复。"""
    client, _student, _club, post, reply = setup_member_club_post_and_reply()
    post.status = "已删除"
    post.save()

    resp = client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({"reason": "不当言论"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "POST_DELETED"


def test_report_reply_non_member():
    """非成员不能举报回复。"""
    client, _student, _club, _post, reply = setup_member_club_post_and_reply()

    other_client, _other = login_as_student(username="other_student")

    resp = other_client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({"reason": "不当言论"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_MEMBER"


def test_report_reply_unauthenticated():
    """未认证用户不能举报回复。"""
    client, _student, _club, _post, reply = setup_member_club_post_and_reply()
    unauth_client = Client()
    resp = unauth_client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({"reason": "不当言论"}),
        content_type="application/json",
    )

    assert resp.status_code == 401


def test_report_reply_rejects_disallowed_fields():
    """拒绝不允许的字段。"""
    client, _student, _club, _post, reply = setup_member_club_post_and_reply()

    resp = client.post(
        f"/api/replies/{reply.id}/reports",
        data=json.dumps({"reason": "不当言论", "status": "已采纳"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_report_reply_not_found():
    """不存在的回复返回 404。"""
    client, _student, _club, _post, _reply = setup_member_club_post_and_reply()

    resp = client.post(
        "/api/replies/99999/reports",
        data=json.dumps({"reason": "不当言论"}),
        content_type="application/json",
    )

    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# GET /api/leader/clubs/{club_id}/reports — 查看举报列表
# ═══════════════════════════════════════════════════════════════


def test_leader_reports_empty():
    """无举报时返回空列表。"""
    client, _student, club = setup_leader_and_club()

    resp = client.get(f"/api/leader/clubs/{club.id}/reports")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


def test_leader_reports_with_data():
    """有举报时返回列表。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    # 另一个成员举报
    member = create_student(username="member_student")
    create_test_membership(member, club)
    create_test_report(reporter=member, post=post)

    resp = client.get(f"/api/leader/clubs/{club.id}/reports")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["reason"] == "测试举报"
    assert body["data"]["items"][0]["target"] is not None


def test_leader_reports_includes_target():
    """举报列表包含 target 信息。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student, title="违规帖子")

    member = create_student(username="member_student")
    create_test_membership(member, club)
    create_test_report(reporter=member, post=post)

    resp = client.get(f"/api/leader/clubs/{club.id}/reports")

    body = response_body(resp)
    target = body["data"]["items"][0]["target"]
    assert target["id"] == post.id
    assert target["title"] == "违规帖子"
    assert target["author"]["username"] == student.username


def test_leader_reports_reply_target():
    """回复举报的 target 包含回复信息。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)
    reply = create_test_reply(post, student, content="违规回复")

    member = create_student(username="member_student")
    create_test_membership(member, club)
    create_test_report(reporter=member, reply=reply)

    resp = client.get(f"/api/leader/clubs/{club.id}/reports")

    body = response_body(resp)
    target = body["data"]["items"][0]["target"]
    assert target["id"] == reply.id
    assert target["content"] == "违规回复"


def test_leader_reports_pagination():
    """举报列表支持分页。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    member = create_student(username="member_student")
    create_test_membership(member, club)

    for i in range(5):
        create_test_report(reporter=member, post=post, reason=f"举报{i}")

    resp = client.get(f"/api/leader/clubs/{club.id}/reports?page=1&page_size=2")

    body = response_body(resp)
    assert len(body["data"]["items"]) == 2
    assert body["data"]["total"] == 5


def test_leader_reports_not_leader():
    """非负责人不能查看举报。"""
    client, _student, club, _membership = setup_member_and_club()
    post = create_test_post(club, _student)

    resp = client.get(f"/api/leader/clubs/{club.id}/reports")

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_LEADER"


def test_leader_reports_unauthenticated():
    """未认证用户不能查看举报。"""
    client = Client()
    resp = client.get("/api/leader/clubs/1/reports")

    assert resp.status_code == 401


def test_leader_reports_only_own_club():
    """负责人只能查看自己社团的举报。"""
    client, _student, club1 = setup_leader_and_club()

    # 另一个社团及其负责人
    other_leader = create_student(username="other_leader")
    club2 = create_test_club(name="其他社团")
    create_test_membership(other_leader, club2, club_role="leader")
    post = create_test_post(club2, other_leader)
    create_test_report(reporter=other_leader, post=post)

    resp = client.get(f"/api/leader/clubs/{club1.id}/reports")

    body = response_body(resp)
    assert len(body["data"]["items"]) == 0  # 不应包含 club2 的举报


# ═══════════════════════════════════════════════════════════════
# POST /api/leader/reports/{report_id}/process — 处理举报
# ═══════════════════════════════════════════════════════════════


def test_process_report_accept_no_delete():
    """采纳举报但不删除目标。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    member = create_student(username="member_student")
    create_test_membership(member, club)
    report = create_test_report(reporter=member, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "确实存在违规内容",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已采纳"
    assert body["data"]["processing_note"] == "确实存在违规内容"

    # 帖子未被删除
    post.refresh_from_db()
    assert post.status == "正常"

    # 生成了通知
    from clubs.models import Notification
    notif = Notification.objects.filter(recipient=member, type="我的举报已经处理").first()
    assert notif is not None


def test_process_report_accept_and_delete_post():
    """采纳举报并删除帖子。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    member = create_student(username="member_student")
    create_test_membership(member, club)
    report = create_test_report(reporter=member, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "确认违规，删除帖子",
            "delete_target": True,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["status"] == "已采纳"

    # 帖子被删除
    post.refresh_from_db()
    assert post.status == "已删除"


def test_process_report_accept_and_delete_reply():
    """采纳举报并删除回复。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)
    reply = create_test_reply(post, student)

    member = create_student(username="member_student")
    create_test_membership(member, club)
    report = create_test_report(reporter=member, reply=reply)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "确认违规，删除回复",
            "delete_target": True,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 200

    reply.refresh_from_db()
    assert reply.status == "已删除"


def test_process_report_not_accepted():
    """未采纳举报。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    member = create_student(username="member_student")
    create_test_membership(member, club)
    report = create_test_report(reporter=member, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "未采纳",
            "processing_note": "经审核无违规内容",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["status"] == "未采纳"

    # 帖子未被删除
    post.refresh_from_db()
    assert post.status == "正常"


def test_process_report_missing_processing_note():
    """处理举报缺失处理说明。"""
    client, _student, club = setup_leader_and_club()
    post = create_test_post(club, _student)
    report = create_test_report(reporter=_student, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "PROCESSING_NOTE_REQUIRED"


def test_process_report_empty_processing_note():
    """处理说明为空白时返回错误。"""
    client, _student, club = setup_leader_and_club()
    post = create_test_post(club, _student)
    report = create_test_report(reporter=_student, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "   ",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "PROCESSING_NOTE_REQUIRED"


def test_process_report_already_processed():
    """已处理举报不能重复处理。"""
    client, _student, club = setup_leader_and_club()
    post = create_test_post(club, _student)
    report = create_test_report(reporter=_student, post=post, status="已采纳")

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "未采纳",
            "processing_note": "想改结论",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "REPORT_ALREADY_PROCESSED"


def test_process_report_invalid_status():
    """无效的处理结论返回错误。"""
    client, _student, club = setup_leader_and_club()
    post = create_test_post(club, _student)
    report = create_test_report(reporter=_student, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "无效状态",
            "processing_note": "测试",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REPORT_STATUS"


def test_process_report_not_accepted_with_delete():
    """未采纳时不能请求删除目标。"""
    client, _student, club = setup_leader_and_club()
    post = create_test_post(club, _student)
    report = create_test_report(reporter=_student, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "未采纳",
            "processing_note": "无违规",
            "delete_target": True,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_DELETE_DECISION"


def test_process_report_not_leader():
    """非负责人不能处理举报。"""
    client, _student, club, _membership = setup_member_and_club()
    report = create_test_report(reporter=_student, post=create_test_post(club, _student))

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "违规",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 403


def test_process_report_wrong_club_leader():
    """其他社团负责人不能处理举报。"""
    client, _student, club1 = setup_leader_and_club()
    post = create_test_post(club1, _student)
    report = create_test_report(reporter=_student, post=post)

    # 另一个社团的负责人
    other_leader = create_student(username="other_leader")
    club2 = create_test_club(name="其他社团")
    create_test_membership(other_leader, club2, club_role="leader")
    other_client = Client()
    login(other_client, "other_leader", "StrongPass!2026")

    resp = other_client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "违规",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 403


def test_process_report_unauthenticated():
    """未认证用户不能处理举报。"""
    # 创建数据获得真实 report ID
    _client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)
    report = create_test_report(reporter=student, post=post)

    unauth_client = Client()
    resp = unauth_client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "违规",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 401


def test_process_report_target_already_deleted():
    """原目标已删除时仍可完成处理，不新增内容快照。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)
    post.status = "已删除"
    post.save()

    member = create_student(username="member_student")
    create_test_membership(member, club)
    report = create_test_report(reporter=member, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "目标已被删除，确认举报",
            "delete_target": True,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["status"] == "已采纳"

    # 通知已生成
    from clubs.models import Notification
    notif = Notification.objects.filter(recipient=member, type="我的举报已经处理").first()
    assert notif is not None


def test_process_report_rejects_disallowed_fields():
    """拒绝不允许的字段。"""
    client, _student, club = setup_leader_and_club()
    post = create_test_post(club, _student)
    report = create_test_report(reporter=_student, post=post)

    resp = client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "违规",
            "delete_target": False,
            "extra_field": "不应该存在",
        }),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_process_report_admin_cannot():
    """管理员不能处理举报。"""
    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    # 创建一个举报
    student = create_student(username="some_student")
    club = create_test_club()
    create_test_membership(student, club)
    post = create_test_post(club, student)
    report = create_test_report(reporter=student, post=post)

    resp = admin_client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "违规",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 403


def test_process_report_not_found():
    """不存在的举报返回 404。"""
    client, _student, _club = setup_leader_and_club()

    resp = client.post(
        "/api/leader/reports/99999/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "违规",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 404


def test_process_report_notification_content():
    """处理举报生成的通知内容正确。"""
    client, student, club = setup_leader_and_club()
    post = create_test_post(club, student)

    member = create_student(username="member_student")
    create_test_membership(member, club)
    report = create_test_report(reporter=member, post=post)

    client.post(
        f"/api/leader/reports/{report.id}/process",
        data=json.dumps({
            "status": "已采纳",
            "processing_note": "确认违规",
            "delete_target": False,
        }),
        content_type="application/json",
    )

    from clubs.models import Notification
    notif = Notification.objects.filter(recipient=member, type="我的举报已经处理").first()
    assert notif is not None
    assert "已采纳" in notif.content
