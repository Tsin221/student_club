"""S07 入社申请、审核、成员创建与通知 — 后端测试。"""

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

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


def login_as_admin():
    admin = create_admin()
    client = Client()
    resp = login(client, admin.username, "AdminPass!2026")
    assert resp.status_code == 200
    return client, admin


def login_as_student():
    student = create_student()
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


def create_test_recruitment(club, publisher, **overrides):
    from clubs.models import Recruitment

    now = timezone.now()
    data = {
        "title": "测试招新",
        "introduction": "招新简介",
        "requirements": "招新要求",
        "capacity": 30,
        "start_time": now - timedelta(days=1),
        "end_time": now + timedelta(days=30),
        "club": club,
        "publisher": publisher,
        **overrides,
    }
    return Recruitment.objects.create(**data)


# ═══════════════════════════════════════════════════════════════
# 学生提交申请 POST /api/recruitments/{id}/applications
# ═══════════════════════════════════════════════════════════════


def test_submit_application_success():
    """正常提交入社申请。"""
    client, student = login_as_student()
    _, leader = login_as_admin()
    #创建另一个学生作为负责人
    leader_user = create_student(username="leader1", name="负责人")
    club = create_test_club()
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    resp = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "我很想加入"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "待审核"
    assert body["data"]["reason"] == "我很想加入"
    assert body["data"]["applicant_id"] == student.id
    assert body["data"]["applicant_name_snapshot"] == student.name
    assert body["data"]["applicant_major_class_snapshot"] == student.major_class
    assert body["data"]["club"]["id"] == club.id
    assert body["data"]["recruitment"]["id"] == recruitment.id


def test_submit_application_no_reason():
    """空申请理由被拒绝。"""
    client, _student = login_as_student()
    _, leader = login_as_admin()
    leader_user = create_student(username="leader2", name="负责人")
    club = create_test_club(name="空理由测试社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    resp = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_submit_application_unauthenticated():
    """未登录不能提交申请。"""
    client = Client()
    resp = client.post(
        "/api/recruitments/1/applications",
        data=json.dumps({"reason": "test"}),
        content_type="application/json",
    )

    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_submit_application_duplicate_pending():
    """同一招新下不能有重复待审核申请。"""
    client, student = login_as_student()
    leader_user = create_student(username="leader3", name="负责人")
    club = create_test_club(name="重复申请测试社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    #第一次提交
    resp1 = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "第一次申请"}),
        content_type="application/json",
    )
    assert resp1.status_code == 201

    #第二次提交
    resp2 = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "第二次申请"}),
        content_type="application/json",
    )

    assert resp2.status_code == 409
    assert response_body(resp2)["code"] == "PENDING_APPLICATION_EXISTS"


def test_submit_application_already_member():
    """已在社成员不能提交申请。"""
    client, student = login_as_student()
    leader_user = create_student(username="leader4", name="负责人")
    club = create_test_club(name="成员申请测试社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    create_test_membership(student, club, member_status="active", club_role="member")
    recruitment = create_test_recruitment(club, leader_user)

    resp = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "我想申请"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "ALREADY_CLUB_MEMBER"


def test_submit_application_recruitment_not_started():
    """招新未开始时不能申请。"""
    client, _student = login_as_student()
    leader_user = create_student(username="leader5", name="负责人")
    club = create_test_club(name="未开始招新社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    now = timezone.now()
    recruitment = create_test_recruitment(
        club, leader_user,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=30),
    )

    resp = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "我想申请"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "RECRUITMENT_NOT_STARTED"


def test_submit_application_recruitment_ended():
    """招新已结束时不能申请。"""
    client, _student = login_as_student()
    leader_user = create_student(username="leader6", name="负责人")
    club = create_test_club(name="已结束招新社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    now = timezone.now()
    recruitment = create_test_recruitment(
        club, leader_user,
        start_time=now - timedelta(days=30),
        end_time=now - timedelta(days=1),
    )

    resp = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "我想申请"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "RECRUITMENT_ENDED"


def test_submit_application_recruitment_full():
    """招新已满时不能申请。"""
    client, student = login_as_student()
    leader_user = create_student(username="leader7", name="负责人")
    club = create_test_club(name="已满招新社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user, capacity=0)

    resp = client.post(
        f"/api/recruitments/{recruitment.id}/applications",
        data=json.dumps({"reason": "我想申请"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "RECRUITMENT_FULL"


def test_submit_application_not_later_recruitment():
    """被拒绝后只能申请后续新招新。"""
    from clubs.models import JoinApplication

    client, student = login_as_student()
    leader_user = create_student(username="leader8", name="负责人")
    club = create_test_club(name="往期招新社团")

    #创建一条已拒绝的旧申请
    old_recruitment = create_test_recruitment(
        club, leader_user,
        title="旧招新",
    )
    JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=old_recruitment,
        reason="旧申请",
        status=JoinApplication.Status.REJECTED,
    )

    #尝试申请同一条旧招新（往期）
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    resp = client.post(
        f"/api/recruitments/{old_recruitment.id}/applications",
        data=json.dumps({"reason": "再次申请同一条"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "NOT_LATER_RECRUITMENT"


# ═══════════════════════════════════════════════════════════════
# 学生查看本人申请 GET /api/me/join-applications
# ═══════════════════════════════════════════════════════════════


def test_my_applications_empty():
    """无申请时返回空列表。"""
    client, _student = login_as_student()

    resp = client.get("/api/me/join-applications")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


def test_my_applications_with_data():
    """有申请时返回正确列表。"""
    from clubs.models import JoinApplication

    client, student = login_as_student()
    leader_user = create_student(username="leader9", name="负责人")
    club = create_test_club(name="我的申请社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.PENDING,
    )

    resp = client.get("/api/me/join-applications")
    assert resp.status_code == 200
    body = response_body(resp)
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["status"] == "待审核"
    assert body["data"]["items"][0]["reason"] == "申请理由"


# ═══════════════════════════════════════════════════════════════
# 负责人查看申请 GET /api/leader/clubs/{id}/join-applications
# ═══════════════════════════════════════════════════════════════


def test_leader_applications():
    """负责人可查看本社团申请。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader10", name="负责人")
    club = create_test_club(name="负责人查看申请社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
    )

    #以负责人身份登录
    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.get(f"/api/leader/clubs/{club.id}/join-applications")
    assert resp.status_code == 200
    body = response_body(resp)
    assert len(body["data"]["items"]) == 1


def test_leader_applications_not_leader():
    """非负责人不能查看。"""
    client, _student = login_as_student()
    leader_user = create_student(username="leader11", name="负责人")
    club = create_test_club(name="非负责人查看社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")

    resp = client.get(f"/api/leader/clubs/{club.id}/join-applications")
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# 负责人通过申请 POST /api/leader/join-applications/{id}/approve
# ═══════════════════════════════════════════════════════════════


def test_approve_application_success():
    """通过申请：创建成员关系 + 生成通知。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader12", name="负责人")
    club = create_test_club(name="通过申请社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    app = JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.PENDING,
    )

    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.post(
        f"/api/leader/join-applications/{app.id}/approve",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["application"]["status"] == "已通过"
    assert body["data"]["membership"]["member_status"] == "active"
    assert body["data"]["membership"]["club_role"] == "member"
    assert body["data"]["membership"]["user_id"] == student.id

    #验证成员关系已创建
    from clubs.models import ClubMembership
    membership = ClubMembership.objects.get(user=student, club=club)
    assert membership.member_status == "active"
    assert membership.club_role == "member"

    #验证通知已生成
    from clubs.models import Notification
    notifs = Notification.objects.filter(recipient=student)
    assert notifs.count() == 1
    assert notifs[0].type == "我的入社申请已经审核"


def test_approve_application_restore_membership():
    """通过申请时恢复已退出成员关系。"""
    from clubs.models import ClubMembership, JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader13", name="负责人")
    club = create_test_club(name="恢复成员社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")

    #创建一条已退出的成员关系
    ClubMembership.objects.create(
        user=student,
        club=club,
        member_status="exited",
        club_role="member",
    )

    recruitment = create_test_recruitment(club, leader_user)
    app = JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="重新申请",
        status=JoinApplication.Status.PENDING,
    )

    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.post(
        f"/api/leader/join-applications/{app.id}/approve",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["membership"]["member_status"] == "active"

    #验证只有一条关系
    membership_count = ClubMembership.objects.filter(user=student, club=club).count()
    assert membership_count == 1


def test_approve_application_not_pending():
    """不能通过已处理的申请。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader14", name="负责人")
    club = create_test_club(name="重复通过社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    app = JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.APPROVED,
    )

    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.post(
        f"/api/leader/join-applications/{app.id}/approve",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "APPLICATION_NOT_PENDING"


def test_approve_application_recruitment_full():
    """容量已满时不能通过。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader15", name="负责人")
    club = create_test_club(name="容量满社团")

    #先通过一个人占满容量
    other_student = create_student(username="other_student", name="其他学生")
    create_test_membership(other_student, club, member_status="active", club_role="member")

    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user, capacity=1)

    #创建一个已通过的申请占满容量
    JoinApplication.objects.create(
        applicant=other_student,
        applicant_name_snapshot=other_student.name,
        applicant_major_class_snapshot=other_student.major_class,
        club=club,
        recruitment=recruitment,
        reason="已通过",
        status=JoinApplication.Status.APPROVED,
    )

    app = JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.PENDING,
    )

    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.post(
        f"/api/leader/join-applications/{app.id}/approve",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "RECRUITMENT_FULL"


def test_approve_application_not_leader():
    """非负责人不能通过申请。"""
    from clubs.models import JoinApplication

    student_applicant = create_student(username="student_applicant", name="申请人")
    student_other = create_student(username="student_other", name="其他学生")
    leader_user = create_student(username="leader16", name="负责人")
    club = create_test_club(name="非负责人通过社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    app = JoinApplication.objects.create(
        applicant=student_applicant,
        applicant_name_snapshot=student_applicant.name,
        applicant_major_class_snapshot=student_applicant.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.PENDING,
    )

    #以普通学生登录（非负责人）
    client = Client()
    login(client, student_other.username, "StrongPass!2026")
    resp = client.post(
        f"/api/leader/join-applications/{app.id}/approve",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# 负责人拒绝申请 POST /api/leader/join-applications/{id}/reject
# ═══════════════════════════════════════════════════════════════


def test_reject_application_success():
    """拒绝申请：生成通知。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader17", name="负责人")
    club = create_test_club(name="拒绝申请社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    app = JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.PENDING,
    )

    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.post(
        f"/api/leader/join-applications/{app.id}/reject",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已拒绝"

    #验证通知
    from clubs.models import Notification
    notifs = Notification.objects.filter(recipient=student)
    assert notifs.count() == 1


def test_reject_application_not_pending():
    """不能拒绝已处理的申请。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader18", name="负责人")
    club = create_test_club(name="重复拒绝社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    app = JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
        status=JoinApplication.Status.REJECTED,
    )

    leader_client = Client()
    login(leader_client, leader_user.username, "StrongPass!2026")

    resp = leader_client.post(
        f"/api/leader/join-applications/{app.id}/reject",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "APPLICATION_NOT_PENDING"


# ═══════════════════════════════════════════════════════════════
# 管理员查看全量申请 GET /api/admin/join-applications
# ═══════════════════════════════════════════════════════════════


def test_admin_applications():
    """管理员可查看全量申请。"""
    from clubs.models import JoinApplication

    _, student = login_as_student()
    leader_user = create_student(username="leader19", name="负责人")
    club = create_test_club(name="管理员查看社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user)

    JoinApplication.objects.create(
        applicant=student,
        applicant_name_snapshot=student.name,
        applicant_major_class_snapshot=student.major_class,
        club=club,
        recruitment=recruitment,
        reason="申请理由",
    )

    admin_client, _admin = login_as_admin()
    resp = admin_client.get("/api/admin/join-applications")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] >= 1


def test_admin_applications_readonly():
    """管理员只能查看，不能申请。"""
    admin_client, _admin = login_as_admin()
    resp = admin_client.post(
        "/api/recruitments/1/applications",
        data=json.dumps({"reason": "管理员尝试申请"}),
        content_type="application/json",
    )

    assert resp.status_code in (403, 404)


# ═══════════════════════════════════════════════════════════════
# 学生查看通知 GET /api/me/notifications
# ═══════════════════════════════════════════════════════════════


def test_my_notifications_empty():
    """无通知时返回空列表。"""
    client, _student = login_as_student()

    resp = client.get("/api/me/notifications")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["items"] == []


def test_my_notifications_with_data():
    """有通知时返回正确数据。"""
    from clubs.models import Notification

    _, student = login_as_student()
    Notification.objects.create(
        recipient=student,
        type=Notification.Type.APPLICATION_REVIEWED,
        content="你的入社申请已通过",
    )

    client = Client()
    login(client, student.username, "StrongPass!2026")

    resp = client.get("/api/me/notifications")
    assert resp.status_code == 200
    body = response_body(resp)
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["type"] == "我的入社申请已经审核"
    assert body["data"]["items"][0]["content"] == "你的入社申请已通过"


# ═══════════════════════════════════════════════════════════════
# 已通过人数统计（serializer compute_recruitment_status）
# ═══════════════════════════════════════════════════════════════


def test_approved_count_in_recruitment():
    """招新已通过人数正确反映已通过申请数。"""
    from clubs.models import JoinApplication
    from clubs.serializers import serialize_recruitment

    leader_user = create_student(username="leader20", name="负责人")
    club = create_test_club(name="计数测试社团")
    create_test_membership(leader_user, club, member_status="active", club_role="leader")
    recruitment = create_test_recruitment(club, leader_user, capacity=10)

    student_a = create_student(username="student_a", name="学生A")
    student_b = create_student(username="student_b", name="学生B")

    JoinApplication.objects.create(
        applicant=student_a,
        applicant_name_snapshot=student_a.name,
        applicant_major_class_snapshot=student_a.major_class,
        club=club,
        recruitment=recruitment,
        reason="理由",
        status=JoinApplication.Status.APPROVED,
    )
    JoinApplication.objects.create(
        applicant=student_b,
        applicant_name_snapshot=student_b.name,
        applicant_major_class_snapshot=student_b.major_class,
        club=club,
        recruitment=recruitment,
        reason="理由",
        status=JoinApplication.Status.PENDING,
    )

    result = serialize_recruitment(recruitment)
    assert result["approved_count"] == 1
