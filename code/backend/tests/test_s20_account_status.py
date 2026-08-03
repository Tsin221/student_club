import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from clubs.models import Club, ClubMembership

LOGIN_URL = "/api/auth/login"


def response_body(response):
    return json.loads(response.content)


def post_json(client, url, data):
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


def patch_json(client, url, data):
    return client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


VALID_STUDENT = {
    "username": "s20_test_student",
    "password": "StrongPass!2026",
    "name": "测试学生",
    "phone": "13800001111",
    "major_class": "计算机1班",
    "grade": "2026",
}


def create_user(**overrides):
    data = {**VALID_STUDENT, **overrides}
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


def login_as_admin():
    admin = create_admin()
    client = Client()
    login_resp = client.post(
        LOGIN_URL,
        data=json.dumps({
            "username": admin.username,
            "password": "AdminPass!2026",
        }),
        content_type="application/json",
    )
    assert login_resp.status_code == 200
    return client, admin


def login_as_student(student, password="StrongPass!2026"):
    client = Client()
    login_resp = client.post(
        LOGIN_URL,
        data=json.dumps({
            "username": student.username,
            "password": password,
        }),
        content_type="application/json",
    )
    return client, login_resp


def create_club(name, category=Club.Category.OTHER):
    return Club.objects.create(
        name=name,
        category=category,
        introduction="测试社团",
        logo="/media/logos/test.png",
        status=Club.Status.ACTIVE,
    )


def create_leader_membership(user, club):
    return ClubMembership.objects.create(
        user=user,
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club_role=ClubMembership.ClubRole.LEADER,
    )


def status_url(user_id):
    return f"/api/admin/users/{user_id}/status"


# ── 正常路径 ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_admin_can_disable_student():
    """管理员可以停用学生账号。"""
    student = create_user()
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["account_status"] == "disabled"

    student.refresh_from_db()
    assert student.account_status == "disabled"


@pytest.mark.django_db
def test_admin_can_restore_student():
    """管理员可以恢复已停用的学生账号。"""
    student = create_user(account_status="disabled")
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "active"},
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["account_status"] == "active"

    student.refresh_from_db()
    assert student.account_status == "active"


@pytest.mark.django_db
def test_same_status_no_change():
    """相同状态不产生实际变更，但返回成功。"""
    student = create_user()
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "active"},
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["account_status"] == "active"


# ── 停用后登录与会话校验 ──────────────────────────────────────


@pytest.mark.django_db
def test_disabled_account_cannot_login():
    """停用后新登录被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    # 停用
    patch_json(client, status_url(student.id), {"account_status": "disabled"})

    # 尝试登录
    login_client = Client()
    response = login_client.post(
        LOGIN_URL,
        data=json.dumps({
            "username": student.username,
            "password": "StrongPass!2026",
        }),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "ACCOUNT_DISABLED"


@pytest.mark.django_db
def test_disabled_account_existing_session_rejected():
    """停用后已有会话访问受保护接口被拒绝。"""
    student = create_user()
    admin_client, _ = login_as_admin()

    # 学生先登录
    student_client, login_resp = login_as_student(student)
    assert login_resp.status_code == 200

    # 管理员停用该学生
    patch_json(admin_client, status_url(student.id), {"account_status": "disabled"})

    # 学生已有会话尝试访问受保护接口
    response = student_client.get("/api/me/profile")

    assert response.status_code == 403
    assert response_body(response)["code"] == "ACCOUNT_DISABLED"


# ── 最后有效负责人保护 ────────────────────────────────────────


@pytest.mark.django_db
def test_disable_last_effective_leader_rejected():
    """停用社团唯一有效负责人被拒绝。"""
    student = create_user()
    club = create_club("测试社团")
    create_leader_membership(student, club)
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 409
    assert response_body(response)["code"] == "LAST_EFFECTIVE_LEADER"

    # 账号状态未改变
    student.refresh_from_db()
    assert student.account_status == "active"


@pytest.mark.django_db
def test_disable_last_effective_leader_multiple_clubs():
    """如果学生在多个社团都是最后有效负责人，任一处缺失即拒绝。"""
    student = create_user()
    club_a = create_club("社团A")
    club_b = create_club("社团B")
    create_leader_membership(student, club_a)
    create_leader_membership(student, club_b)
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 409
    assert response_body(response)["code"] == "LAST_EFFECTIVE_LEADER"

    student.refresh_from_db()
    assert student.account_status == "active"


@pytest.mark.django_db
def test_disable_non_last_leader_succeeds():
    """停用非最后有效负责人成功——同社团还有其他有效负责人。"""
    student_a = create_user(username="leader_a", name="负责人A")
    student_b = create_user(username="leader_b", name="负责人B")
    club = create_club("多人负责社团")
    create_leader_membership(student_a, club)
    create_leader_membership(student_b, club)
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student_a.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 200
    student_a.refresh_from_db()
    assert student_a.account_status == "disabled"


@pytest.mark.django_db
def test_disable_student_not_leader_succeeds():
    """不是负责人的普通学生可以直接停用。"""
    student = create_user()
    club = create_club("其他社团")
    # 学生只是普通成员，不是负责人
    ClubMembership.objects.create(
        user=student,
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club_role=ClubMembership.ClubRole.MEMBER,
    )
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 200
    student.refresh_from_db()
    assert student.account_status == "disabled"


@pytest.mark.django_db
def test_disable_does_not_affect_cancelled_club():
    """已注销社团的负责人不阻止停用。"""
    student = create_user()
    club = create_club("已注销社团")
    club.status = Club.Status.CANCELLED
    club.save()
    create_leader_membership(student, club)
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 200
    student.refresh_from_db()
    assert student.account_status == "disabled"


# ── 停用不删除数据 ────────────────────────────────────────────


@pytest.mark.django_db
def test_disable_preserves_memberships():
    """停用不删除成员关系。"""
    student = create_user()
    club = create_club("保留社团")
    # 其他负责人保护
    other = create_user(username="other_leader", name="另一负责人")
    create_leader_membership(other, club)
    create_leader_membership(student, club)
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 200
    # 成员关系仍存在
    assert ClubMembership.objects.filter(user=student, club=club).exists()


@pytest.mark.django_db
def test_restore_only_restores_login():
    """恢复只恢复登录资格，不修改成员状态和社团身份。"""
    student = create_user(account_status="disabled")
    club = create_club("恢复测试社团")
    # 停用前已经是负责人
    ClubMembership.objects.create(
        user=student,
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club_role=ClubMembership.ClubRole.LEADER,
    )
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "active"},
    )

    assert response.status_code == 200
    student.refresh_from_db()
    assert student.account_status == "active"

    # 成员关系状态未变
    membership = ClubMembership.objects.get(user=student, club=club)
    assert membership.member_status == ClubMembership.MemberStatus.ACTIVE
    assert membership.club_role == ClubMembership.ClubRole.LEADER


# ── 权限拒绝 ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_status_update_rejects_unauthenticated():
    """未登录不能操作。"""
    student = create_user()
    response = patch_json(
        Client(),
        status_url(student.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_status_update_rejects_student():
    """学生不能操作他人状态。"""
    student = create_user()
    other = create_user(username="other_student", name="其他学生")
    client = Client()
    client.force_login(student)

    response = patch_json(
        client,
        status_url(other.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_status_update_rejects_nonexistent_user():
    """目标用户不存在时返回 RESOURCE_NOT_FOUND。"""
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(99999),
        {"account_status": "disabled"},
    )

    assert response.status_code == 404
    assert response_body(response)["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.django_db
def test_status_update_rejects_admin_target():
    """不能操作管理员账号状态。"""
    admin2 = create_admin(username="admin2", password="Admin2Pass!2026")
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(admin2.id),
        {"account_status": "disabled"},
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "NOT_STUDENT_USER"


# ── 请求校验 ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_status_update_rejects_invalid_status():
    """非法状态值被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "banned"},
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_status_update_rejects_missing_field():
    """缺少 account_status 字段被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {},
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_status_update_rejects_extra_fields():
    """包含多余字段被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    response = patch_json(
        client,
        status_url(student.id),
        {"account_status": "disabled", "extra": "field"},
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_status_update_rejects_wrong_method():
    """非 PATCH 方法被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    response = client.post(
        status_url(student.id),
        data=json.dumps({"account_status": "disabled"}),
        content_type="application/json",
    )

    assert response.status_code == 405
    assert response_body(response)["code"] == "INVALID_REQUEST"
