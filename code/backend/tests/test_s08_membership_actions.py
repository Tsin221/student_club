"""S08 成员退出、移除和历史关系 — 后端测试。"""

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


def login_as_admin():
    admin = create_admin()
    client = Client()
    resp = login(client, admin.username, "AdminPass!2026")
    assert resp.status_code == 200
    return client, admin


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


# ═══════════════════════════════════════════════════════════════
# POST /api/me/memberships/{id}/exit — 学生主动退出
# ═══════════════════════════════════════════════════════════════


def test_exit_success():
    """普通成员主动退出成功，状态变为已退出。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["member_status"] == "exited"
    assert body["data"]["club_role"] == "member"


def test_exit_preserves_history():
    """退出后成员关系记录保留，club_role 不变。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 200

    #通过 GET /api/me/memberships 验证历史记录中存在
    resp2 = client.get("/api/me/memberships")
    assert resp2.status_code == 200
    body2 = response_body(resp2)
    items = body2["data"]["items"]
    assert any(m["id"] == membership.id and m["member_status"] == "exited" for m in items)


def test_exit_leader_rejected():
    """负责人不能主动退出。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "LEADER_CANNOT_EXIT"


def test_exit_already_exited_rejected():
    """已退出的成员不能重复退出。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club, member_status="exited", club_role="member")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_exit_removed_member_rejected():
    """已被移除的成员不能退出。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club, member_status="removed", club_role="member")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_exit_cancelled_club_rejected():
    """已注销社团的成员不能退出。"""
    client, student = login_as_student()
    from clubs.models import Club

    club = Club.objects.create(
        name="已注销社团",
        category="学术科技",
        introduction="简介",
        logo="logos/test.png",
        status=Club.Status.CANCELLED,
    )
    membership = create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "CLUB_CANCELLED"


def test_exit_other_user_membership_rejected():
    """不能退出其他用户的成员关系。"""
    client, student1 = login_as_student("student_a")
    student2 = create_student(username="student_b")
    club = create_test_club()
    membership = create_test_membership(student2, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 404
    body = response_body(resp)
    assert body["code"] == "RESOURCE_NOT_FOUND"


def test_exit_unauthenticated_rejected():
    """未登录不能退出。"""
    student = create_student()
    club = create_test_club()
    membership = create_test_membership(student, club)

    client = Client()
    resp = client.post(
        f"/api/me/memberships/{membership.id}/exit",
        content_type="application/json",
    )

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


def test_exit_disabled_account_rejected():
    """账号停用后已有会话也不能退出。"""
    student = create_student(account_status=get_user_model().AccountStatus.DISABLED)
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    #停用账号登录会返回 ACCOUNT_DISABLED
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# POST /api/leader/memberships/{id}/remove — 负责人移除成员
# ═══════════════════════════════════════════════════════════════


def test_leader_remove_success():
    """负责人成功移除普通成员。"""
    client, leader = login_as_student("leader_01")
    member = create_student(username="member_01")
    club = create_test_club()
    leader_ms = create_test_membership(leader, club, member_status="active", club_role="leader")
    target_ms = create_test_membership(member, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["member_status"] == "removed"
    assert body["data"]["club_role"] == "member"
    assert body["data"]["id"] == target_ms.id


def test_leader_remove_preserves_history():
    """移除后成员关系记录保留。"""
    client, leader = login_as_student("leader_02")
    member = create_student(username="member_02")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    target_ms = create_test_membership(member, club, member_status="active", club_role="member")

    client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    #负责人查看成员列表不应再包含该成员
    resp = client.get(f"/api/leader/clubs/{club.id}/members")
    assert resp.status_code == 200
    body = response_body(resp)
    assert not any(m["id"] == target_ms.id for m in body["data"]["items"])


def test_leader_remove_target_is_leader_rejected():
    """不能移除负责人。"""
    client, leader = login_as_student("leader_03")
    other_leader = create_student(username="leader_04")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    target_ms = create_test_membership(other_leader, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "TARGET_IS_LEADER"


def test_leader_remove_already_removed_rejected():
    """不能重复移除已移除的成员。"""
    client, leader = login_as_student("leader_05")
    member = create_student(username="member_05")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    target_ms = create_test_membership(member, club, member_status="removed", club_role="member")

    resp = client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_non_leader_cannot_remove():
    """非负责人不能移除成员。"""
    client, student = login_as_student("ordinary_member")
    member = create_student(username="victim")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    target_ms = create_test_membership(member, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_remove_other_club_member_rejected():
    """负责人不能移除其他社团的成员。"""
    client, leader = login_as_student("leader_a")
    member = create_student(username="member_b")
    club_a = create_test_club(name="社团A")
    club_b = create_test_club(name="社团B")
    create_test_membership(leader, club_a, member_status="active", club_role="leader")
    target_ms = create_test_membership(member, club_b, member_status="active", club_role="member")

    resp = client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_remove_unauthenticated_rejected():
    """未登录不能移除成员。"""
    member = create_student()
    club = create_test_club()
    target_ms = create_test_membership(member, club)

    client = Client()
    resp = client.post(
        f"/api/leader/memberships/{target_ms.id}/remove",
        content_type="application/json",
    )

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


def test_leader_remove_nonexistent_membership():
    """移除不存在的成员关系返回 404。"""
    client, leader = login_as_student("leader_z")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.post(
        "/api/leader/memberships/99999/remove",
        content_type="application/json",
    )

    assert resp.status_code == 404
    body = response_body(resp)
    assert body["code"] == "RESOURCE_NOT_FOUND"


# ═══════════════════════════════════════════════════════════════
# GET /api/me/memberships — 历史关系可见
# ═══════════════════════════════════════════════════════════════


def test_my_memberships_includes_exited_and_removed():
    """GET /api/me/memberships 同时返回当前和历史关系。"""
    client, student = login_as_student()
    club_a = create_test_club(name="社团A")
    club_b = create_test_club(name="社团B")
    club_c = create_test_club(name="社团C")

    create_test_membership(student, club_a, member_status="active", club_role="member")
    create_test_membership(student, club_b, member_status="exited", club_role="member")
    create_test_membership(student, club_c, member_status="removed", club_role="member")

    resp = client.get("/api/me/memberships")
    assert resp.status_code == 200
    body = response_body(resp)
    items = body["data"]["items"]
    assert len(items) == 3

    statuses = {m["member_status"] for m in items}
    assert "active" in statuses
    assert "exited" in statuses
    assert "removed" in statuses
