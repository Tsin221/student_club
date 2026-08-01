"""S14 意见反馈 — 后端测试。"""

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


# ═══════════════════════════════════════════════════════════════
# POST /api/clubs/{club_id}/feedback — 提交反馈
# ═══════════════════════════════════════════════════════════════


def test_create_feedback_success():
    """在社成员可以成功提交反馈。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "希望增加更多活动"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["content"] == "希望增加更多活动"
    assert body["data"]["status"] == "待处理"
    assert body["data"]["processing_note"] is None
    assert body["data"]["submitter"]["username"] == "test_student"
    assert body["data"]["club"]["name"] == "测试社团"
    assert body["data"]["submitted_at"] is not None


def test_create_feedback_content_stripped():
    """反馈内容首尾空格被去除。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "  有用的建议  "}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["data"]["content"] == "有用的建议"


def test_create_feedback_missing_content():
    """缺少 content 字段返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_create_feedback_empty_content():
    """content 为空字符串返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_create_feedback_whitespace_content():
    """content 只有空白字符返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "   "}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_create_feedback_non_member():
    """非社团成员不能提交反馈。"""
    client, student = login_as_student()
    club = create_test_club()
    #不创建成员关系

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_MEMBER"


def test_create_feedback_ex_member():
    """已退出的成员不能提交反馈。"""
    client, _student, club, membership = setup_member_and_club()

    #退出社团
    membership.member_status = "exited"
    membership.save()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "MEMBERSHIP_INACTIVE"


def test_create_feedback_cancelled_club():
    """已注销社团不能提交反馈。"""
    client, _student, club, _membership = setup_member_and_club()

    club.status = "cancelled"
    club.save()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_create_feedback_unauthenticated():
    """未登录不能提交反馈。"""
    _client, _student, club, _membership = setup_member_and_club()

    anon_client = Client()
    resp = anon_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )

    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_create_feedback_rejects_disallowed_fields():
    """提交不允许的字段返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议", "status": "已处理"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_create_feedback_leader_can_submit():
    """负责人也可以提交反馈。"""
    client, _student, club = setup_leader_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "负责人的意见"}),
        content_type="application/json",
    )

    assert resp.status_code == 201


def test_create_feedback_multiple_allowed():
    """同一成员可以多次提交反馈（无唯一约束）。"""
    client, _student, club, _membership = setup_member_and_club()

    resp1 = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "第一次建议"}),
        content_type="application/json",
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "第二次建议"}),
        content_type="application/json",
    )
    assert resp2.status_code == 201

    #确认两条都创建了
    assert response_body(resp1)["data"]["id"] != response_body(resp2)["data"]["id"]


def test_create_feedback_wrong_method():
    """不支持的 HTTP 方法返回 405。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.get(f"/api/clubs/{club.id}/feedback")

    assert resp.status_code == 405


def test_create_feedback_admin_cannot_submit():
    """管理员不能提交反馈。"""
    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    club = create_test_club()

    resp = admin_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "管理员建议"}),
        content_type="application/json",
    )

    #管理员账号不是学生，require_club_member 中的 require_active_student 会拒绝
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "FORBIDDEN"


# ═══════════════════════════════════════════════════════════════
# GET /api/me/feedback — 查看本人反馈
# ═══════════════════════════════════════════════════════════════


def test_my_feedbacks_empty():
    """没有反馈时返回空列表。"""
    client, _student, _club, _membership = setup_member_and_club()

    resp = client.get("/api/me/feedback")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["items"] == []


def test_my_feedbacks_with_data():
    """提交反馈后可以在列表看到。"""
    client, _student, club, _membership = setup_member_and_club()

    #提交反馈
    client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "增加社团活动"}),
        content_type="application/json",
    )

    resp = client.get("/api/me/feedback")
    assert resp.status_code == 200
    body = response_body(resp)
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["content"] == "增加社团活动"
    assert body["data"]["items"][0]["status"] == "待处理"


def test_my_feedbacks_shows_history():
    """退出社团后仍可查看历史反馈。"""
    client, _student, club, membership = setup_member_and_club()

    #先提交反馈
    client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "历史建议"}),
        content_type="application/json",
    )

    #退出社团
    membership.member_status = "exited"
    membership.save()

    #仍可查看历史
    resp = client.get("/api/me/feedback")
    assert resp.status_code == 200
    assert len(response_body(resp)["data"]["items"]) == 1


def test_my_feedbacks_shows_processed():
    """我的反馈列表包含已处理的反馈。"""
    client, student, club, _membership = setup_member_and_club()

    #提交反馈
    create_resp = client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "待处理建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    #负责人处理反馈
    leader_client, leader = login_as_student(username="fb_leader")
    create_test_membership(leader, club, club_role="leader")
    leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "已处理完成"}),
        content_type="application/json",
    )

    #提交人查看
    resp = client.get("/api/me/feedback")
    items = response_body(resp)["data"]["items"]
    assert len(items) == 1
    assert items[0]["status"] == "已处理"
    assert items[0]["processing_note"] == "已处理完成"


def test_my_feedbacks_unauthenticated():
    """未登录不能查看反馈。"""
    resp = Client().get("/api/me/feedback")
    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_my_feedbacks_only_own():
    """只返回本人的反馈，不返回他人反馈。"""
    client1, _student1, club, _membership1 = setup_member_and_club()

    #另一个学生
    student2 = create_student(username="student_fb")
    client2 = Client()
    login(client2, "student_fb", "StrongPass!2026")
    create_test_membership(student2, club)

    #各自提交反馈
    client1.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "学生1的反馈"}),
        content_type="application/json",
    )
    client2.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "学生2的反馈"}),
        content_type="application/json",
    )

    #学生1只看到自己
    resp1 = client1.get("/api/me/feedback")
    items1 = response_body(resp1)["data"]["items"]
    assert len(items1) == 1
    assert items1[0]["submitter"]["username"] == "test_student"

    #学生2只看到自己
    resp2 = client2.get("/api/me/feedback")
    items2 = response_body(resp2)["data"]["items"]
    assert len(items2) == 1
    assert items2[0]["submitter"]["username"] == "student_fb"


# ═══════════════════════════════════════════════════════════════
# GET /api/leader/clubs/{club_id}/feedback — 负责人查看社团反馈
# ═══════════════════════════════════════════════════════════════


def test_leader_feedbacks_empty():
    """负责人查看空反馈列表。"""
    client, _student, club = setup_leader_and_club()

    resp = client.get(f"/api/leader/clubs/{club.id}/feedback")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


def test_leader_feedbacks_with_data():
    """负责人可以查看社团的全部反馈。"""
    leader_client, leader, club = setup_leader_and_club()

    #学生提交反馈
    student = create_student(username="member_fb1")
    student_client = Client()
    login(student_client, "member_fb1", "StrongPass!2026")
    create_test_membership(student, club)
    student_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "反馈内容1"}),
        content_type="application/json",
    )

    #负责人查看
    resp = leader_client.get(f"/api/leader/clubs/{club.id}/feedback")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 1
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["content"] == "反馈内容1"
    assert body["data"]["items"][0]["submitter"]["username"] == "member_fb1"


def test_leader_feedbacks_pagination():
    """负责人反馈列表分页正常。"""
    client, _student, club = setup_leader_and_club()

    resp = client.get(
        f"/api/leader/clubs/{club.id}/feedback",
        data={"page": "1", "page_size": "10"},
    )
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 10


def test_leader_feedbacks_not_leader():
    """非负责人不能查看社团反馈列表。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, club_role="member")

    resp = client.get(f"/api/leader/clubs/{club.id}/feedback")

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_LEADER"


def test_leader_feedbacks_cancelled_club():
    """已注销社团的反馈不能通过负责人接口查看。"""
    client, _student, club = setup_leader_and_club()

    club.status = "cancelled"
    club.save()

    resp = client.get(f"/api/leader/clubs/{club.id}/feedback")

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_leader_feedbacks_unauthenticated():
    """未登录不能查看负责人反馈列表。"""
    _client, _student, club = setup_leader_and_club()

    resp = Client().get(f"/api/leader/clubs/{club.id}/feedback")

    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_leader_feedbacks_only_own_club():
    """负责人只能查看自己负责社团的反馈。"""
    leader_client, leader, club1 = setup_leader_and_club()

    #创建另一个社团（leader 不是负责人）
    club2 = create_test_club(name="其他社团")

    #其他学生提交反馈到 club2
    student2 = create_student(username="other_member")
    client2 = Client()
    login(client2, "other_member", "StrongPass!2026")
    create_test_membership(student2, club2)
    client2.post(
        f"/api/clubs/{club2.id}/feedback",
        data=json.dumps({"content": "其他社团反馈"}),
        content_type="application/json",
    )

    #本社团也提交一条
    student1 = create_student(username="my_member")
    client1 = Client()
    login(client1, "my_member", "StrongPass!2026")
    create_test_membership(student1, club1)
    client1.post(
        f"/api/clubs/{club1.id}/feedback",
        data=json.dumps({"content": "本社团反馈"}),
        content_type="application/json",
    )

    #负责人查看 club2 的反馈（预期拒绝）
    resp = leader_client.get(f"/api/leader/clubs/{club2.id}/feedback")
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_LEADER"

    #负责人查看 club1 的反馈（预期成功）
    resp = leader_client.get(f"/api/leader/clubs/{club1.id}/feedback")
    assert resp.status_code == 200
    assert response_body(resp)["data"]["total"] == 1


# ═══════════════════════════════════════════════════════════════
# POST /api/leader/feedback/{feedback_id}/process — 负责人处理反馈
# ═══════════════════════════════════════════════════════════════


def test_process_feedback_success_with_note():
    """负责人处理反馈并填写处理说明。"""
    #提交反馈
    member_client, member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    #负责人处理
    leader_client, leader = login_as_student(username="fb_leader")
    create_test_membership(leader, club, club_role="leader")
    resp = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "已采纳，下月开始实施"}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["status"] == "已处理"
    assert body["data"]["processing_note"] == "已采纳，下月开始实施"


def test_process_feedback_success_without_note():
    """负责人处理反馈不填写处理说明（处理说明保持 null）。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    leader_client, leader = login_as_student(username="fb_leader2")
    create_test_membership(leader, club, club_role="leader")
    resp = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["status"] == "已处理"
    assert body["data"]["processing_note"] is None


def test_process_feedback_empty_note():
    """处理说明为空字符串时设为 null。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    leader_client, leader = login_as_student(username="fb_leader3")
    create_test_membership(leader, club, club_role="leader")
    resp = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["status"] == "已处理"
    assert body["data"]["processing_note"] is None


def test_process_feedback_already_processed():
    """已处理的反馈不能重复处理。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    leader_client, leader = login_as_student(username="fb_leader4")
    create_test_membership(leader, club, club_role="leader")

    #第一次处理
    resp1 = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "已处理"}),
        content_type="application/json",
    )
    assert resp1.status_code == 200

    #第二次处理
    resp2 = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "再次处理"}),
        content_type="application/json",
    )
    assert resp2.status_code == 409
    assert response_body(resp2)["code"] == "FEEDBACK_ALREADY_PROCESSED"


def test_process_feedback_not_found():
    """处理不存在的反馈返回 RESOURCE_NOT_FOUND。"""
    client, _student, club = setup_leader_and_club()

    resp = client.post(
        "/api/leader/feedback/99999/process",
        data=json.dumps({"processing_note": "处理"}),
        content_type="application/json",
    )

    assert resp.status_code == 404
    assert response_body(resp)["code"] == "RESOURCE_NOT_FOUND"


def test_process_feedback_not_leader():
    """非负责人不能处理反馈。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    #普通成员尝试处理
    resp = member_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "处理"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_LEADER"


def test_process_feedback_wrong_club_leader():
    """反馈所属社团的其他负责人不能处理。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    #另一个社团的负责人
    other_leader_client, other_leader = login_as_student(username="other_leader")
    other_club = create_test_club(name="其他社团")
    create_test_membership(other_leader, other_club, club_role="leader")

    resp = other_leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "处理"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_LEADER"


def test_process_feedback_cancelled_club():
    """已注销社团的反馈不能处理。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    leader_client, leader = login_as_student(username="fb_leader5")
    create_test_membership(leader, club, club_role="leader")

    #注销社团
    club.status = "cancelled"
    club.save()

    resp = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "处理"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_process_feedback_unauthenticated():
    """未登录不能处理反馈。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    resp = Client().post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "处理"}),
        content_type="application/json",
    )

    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_process_feedback_rejects_disallowed_fields():
    """处理时提交不允许的字段返回错误。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    leader_client, leader = login_as_student(username="fb_leader6")
    create_test_membership(leader, club, club_role="leader")

    resp = leader_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "处理", "status": "其他"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_process_feedback_wrong_method():
    """不支持的 HTTP 方法返回 405。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    leader_client, leader = login_as_student(username="fb_leader7")
    create_test_membership(leader, club, club_role="leader")

    resp = leader_client.get(
        f"/api/leader/feedback/{feedback_id}/process",
    )

    assert resp.status_code == 405


def test_process_feedback_admin_cannot():
    """管理员不能处理反馈。"""
    member_client, _member, club, _membership = setup_member_and_club()
    create_resp = member_client.post(
        f"/api/clubs/{club.id}/feedback",
        data=json.dumps({"content": "建议"}),
        content_type="application/json",
    )
    feedback_id = response_body(create_resp)["data"]["id"]

    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    resp = admin_client.post(
        f"/api/leader/feedback/{feedback_id}/process",
        data=json.dumps({"processing_note": "处理"}),
        content_type="application/json",
    )

    #管理员不是学生角色，require_leader_of_club 会拒绝
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "FORBIDDEN"
