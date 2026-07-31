import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

ADMIN_USERS_URL = "/api/admin/users"
LOGIN_URL = "/api/auth/login"

VALID_STUDENT = {
    "username": "s03_test_student",
    "password": "StrongPass!2026",
    "name": "测试学生",
    "phone": "13800001111",
    "major_class": "计算机1班",
    "grade": "2026",
}


def response_body(response):
    return json.loads(response.content)


def post_json(client, url, data):
    """发送 POST 请求。"""
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


def create_user(**overrides):
    """创建学生用户。"""
    data = {**VALID_STUDENT, **overrides}
    return get_user_model().objects.create_user(**data)


def create_admin(username="admin_test", password="AdminPass!2026"):
    """创建系统管理员。"""
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
    """创建管理员并登录，返回已认证客户端和管理员用户。"""
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


# ── GET /api/admin/users ────────────────────────────────────


@pytest.mark.django_db
def test_admin_can_list_students():
    """管理员可以查看学生列表。"""
    student = create_user()
    client, _ = login_as_admin()

    response = client.get(ADMIN_USERS_URL)

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 20
    assert body["data"]["total"] >= 1
    items = body["data"]["items"]
    student_ids = [item["id"] for item in items]
    assert student.id in student_ids


@pytest.mark.django_db
def test_admin_list_excludes_admin_accounts():
    """管理员列表不包含系统管理员账号。"""
    create_user(username="s1")
    create_user(username="s2")
    create_admin(username="admin1")
    create_admin(username="admin2")
    client, _ = login_as_admin()

    response = client.get(ADMIN_USERS_URL)

    body = response_body(response)
    items = body["data"]["items"]
    roles = {item["platform_role"] for item in items}
    assert "system_admin" not in roles
    student_count = sum(1 for item in items if item["platform_role"] == "student")
    assert student_count >= 2


@pytest.mark.django_db
def test_admin_list_is_paginated():
    """管理员列表支持分页。"""
    for i in range(5):
        create_user(
            username=f"page_student_{i}",
            name=f"分页学生{i}",
        )
    client, _ = login_as_admin()

    response = client.get(f"{ADMIN_USERS_URL}?page=1&page_size=2")

    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    assert len(body["data"]["items"]) <= 2
    assert body["data"]["total"] >= 5


@pytest.mark.django_db
def test_admin_list_returns_empty_when_no_students():
    """没有学生时返回空列表和完整分页结构。"""
    client, _ = login_as_admin()

    response = client.get(ADMIN_USERS_URL)

    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0
    assert body["data"]["page"] == 1


@pytest.mark.django_db
def test_admin_list_response_excludes_password():
    """管理员列表不返回密码或密码哈希。"""
    create_user()
    client, _ = login_as_admin()

    response = client.get(ADMIN_USERS_URL)

    body_str = json.dumps(response_body(response))
    assert "password" not in body_str


@pytest.mark.django_db
def test_admin_list_rejects_invalid_page_params():
    """非法分页参数返回 VALIDATION_ERROR。"""
    client, _ = login_as_admin()

    resp = client.get(f"{ADMIN_USERS_URL}?page_size=200")
    assert resp.status_code == 422
    assert response_body(resp)["code"] == "VALIDATION_ERROR"

    resp = client.get(f"{ADMIN_USERS_URL}?page_size=0")
    assert resp.status_code == 422

    resp = client.get(f"{ADMIN_USERS_URL}?page=0")
    assert resp.status_code == 422


# ── 管理员接口权限 ──────────────────────────────────────────


@pytest.mark.django_db
def test_admin_list_rejects_unauthenticated():
    """未登录不能访问管理员接口。"""
    response = Client().get(ADMIN_USERS_URL)

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_admin_list_rejects_student():
    """学生不能访问管理员接口。"""
    student = create_user()
    client = Client()
    client.force_login(student)

    response = client.get(ADMIN_USERS_URL)

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


# ── POST /api/admin/users/{user_id}/reset-password ──────────


@pytest.mark.django_db
def test_admin_can_reset_student_password():
    """管理员可以重置学生密码，旧密码失效，新密码生效。"""
    student = create_user()
    old_password_hash = student.password
    client, _ = login_as_admin()

    response = post_json(
        client,
        f"/api/admin/users/{student.id}/reset-password",
        {"new_password": "NewStrongPass!2026"},
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["user_id"] == student.id

    student.refresh_from_db()
    assert student.password != old_password_hash
    assert student.check_password("NewStrongPass!2026")
    assert not student.check_password("StrongPass!2026")


@pytest.mark.django_db
def test_reset_password_response_excludes_password():
    """重置密码响应不返回新密码或密码哈希。"""
    student = create_user()
    client, _ = login_as_admin()

    response = post_json(
        client,
        f"/api/admin/users/{student.id}/reset-password",
        {"new_password": "NewStrongPass!2026"},
    )

    body_str = json.dumps(response_body(response))
    assert "NewStrongPass" not in body_str
    assert "password" not in body_str.lower()


@pytest.mark.django_db
def test_reset_password_rejects_weak_password():
    """重置为弱密码时返回 VALIDATION_ERROR。"""
    student = create_user()
    client, _ = login_as_admin()

    response = post_json(
        client,
        f"/api/admin/users/{student.id}/reset-password",
        {"new_password": "12345678"},
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "VALIDATION_ERROR"

    student.refresh_from_db()
    assert student.check_password("StrongPass!2026")


@pytest.mark.django_db
def test_reset_password_rejects_admin_target():
    """不能为管理员账号重置密码。"""
    admin2 = create_admin(username="admin2", password="Admin2Pass!2026")
    client, _ = login_as_admin()

    response = post_json(
        client,
        f"/api/admin/users/{admin2.id}/reset-password",
        {"new_password": "NewStrongPass!2026"},
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "NOT_STUDENT_USER"


@pytest.mark.django_db
def test_reset_password_rejects_nonexistent_user():
    """目标用户不存在时返回 RESOURCE_NOT_FOUND。"""
    client, _ = login_as_admin()

    response = post_json(
        client,
        "/api/admin/users/99999/reset-password",
        {"new_password": "NewStrongPass!2026"},
    )

    assert response.status_code == 404
    assert response_body(response)["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.django_db
def test_reset_password_rejects_empty_password():
    """空密码被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    response = post_json(
        client,
        f"/api/admin/users/{student.id}/reset-password",
        {"new_password": "   "},
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_reset_password_rejects_student_caller():
    """学生不能重置他人密码。"""
    student = create_user()
    other = create_user(username="other_student", name="其他学生")
    client = Client()
    client.force_login(student)

    response = post_json(
        client,
        f"/api/admin/users/{other.id}/reset-password",
        {"new_password": "NewStrongPass!2026"},
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_reset_password_rejects_extra_fields():
    """请求体包含多余字段时被拒绝。"""
    student = create_user()
    client, _ = login_as_admin()

    response = post_json(
        client,
        f"/api/admin/users/{student.id}/reset-password",
        {"new_password": "NewStrongPass!2026", "extra": "field"},
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"
