import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

PROFILE_URL = "/api/me/profile"
CSRF_URL = "/api/auth/csrf"

VALID_STUDENT = {
    "username": "s02_test_user",
    "password": "StrongPass!2026",
    "name": "王同学",
    "phone": "13600000000",
    "major_class": "数据科学1班",
    "grade": "2026",
}


def response_body(response):
    return json.loads(response.content)


def csrf_client():
    """返回一个启用 CSRF 校验且已初始化令牌的测试客户端及令牌。"""
    client = Client(enforce_csrf_checks=True)
    response = client.get(CSRF_URL)
    token = response_body(response)["data"]["csrf_token"]
    return client, token


def patch_json(client, url, data, *, csrf_token):
    """发送带 CSRF 令牌的 PATCH 请求。"""
    return client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )


def create_student(**overrides):
    data = {**VALID_STUDENT, **overrides}
    return get_user_model().objects.create_user(**data)


def login_student():
    """创建正常学生，登录并返回已认证客户端、用户和 CSRF 令牌。"""
    user = create_student()
    client = Client(enforce_csrf_checks=True)
    # 初始化 CSRF Cookie 并获取令牌
    response = client.get(CSRF_URL)
    token = response_body(response)["data"]["csrf_token"]
    # 通过视图登录建立会话
    login_response = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": VALID_STUDENT["username"],
            "password": VALID_STUDENT["password"],
        }),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert login_response.status_code == 200
    return client, user


# ─── 正常流程 ──────────────────────────────────────────────


@pytest.mark.django_db
def test_update_single_field():
    """可以单独修改姓名。"""
    client, user = login_student()
    # PATCH 前重新获取 CSRF 令牌（登录请求已消耗原令牌）
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]
    old_name = user.name

    response = patch_json(
        client,
        PROFILE_URL,
        {"name": "新姓名"},
        csrf_token=csrf_token,
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["name"] == "新姓名"
    assert body["data"]["name"] != old_name
    user.refresh_from_db()
    assert user.name == "新姓名"


@pytest.mark.django_db
def test_update_multiple_fields():
    """可以同时修改多个允许字段。"""
    client, user = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client,
        PROFILE_URL,
        {
            "name": "赵同学",
            "phone": "13711111111",
            "major_class": "人工智能1班",
            "grade": "2025",
        },
        csrf_token=csrf_token,
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["data"]["name"] == "赵同学"
    assert body["data"]["phone"] == "13711111111"
    assert body["data"]["major_class"] == "人工智能1班"
    assert body["data"]["grade"] == "2025"
    user.refresh_from_db()
    assert user.name == "赵同学"
    assert user.phone == "13711111111"


@pytest.mark.django_db
def test_update_phone():
    """可以单独修改手机号。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"phone": "13999999999"}, csrf_token=csrf_token,
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["phone"] == "13999999999"


@pytest.mark.django_db
def test_update_major_class():
    """可以单独修改专业班级。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"major_class": "网络安全2班"}, csrf_token=csrf_token,
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["major_class"] == "网络安全2班"


@pytest.mark.django_db
def test_update_grade():
    """可以单独修改年级。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"grade": "2024"}, csrf_token=csrf_token,
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["grade"] == "2024"


# ─── 请求校验 ──────────────────────────────────────────────


@pytest.mark.django_db
def test_update_rejects_empty_body():
    """空请求体被拒绝。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {}, csrf_token=csrf_token,
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_update_rejects_no_fields():
    """未提交任何字段时被拒绝。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {}, csrf_token=csrf_token,
    )

    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "new_username"),
        ("platform_role", "system_admin"),
        ("account_status", "disabled"),
        ("registered_at", "2026-07-30T10:00:00+08:00"),
        ("avatar", "https://example.com/avatar.png"),
        ("password", "NewPass!2026"),
    ],
)
def test_update_rejects_system_fields(field, value):
    """提交不可修改的系统/头像/密码字段时被拒绝。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {field: value}, csrf_token=csrf_token,
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_update_rejects_system_field_mixed_with_allowed():
    """同时提交允许字段和禁止字段时整次请求被拒绝。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client,
        PROFILE_URL,
        {"name": "新名字", "username": "hacked"},
        csrf_token=csrf_token,
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_update_rejects_empty_string_value():
    """字段值为空字符串时被拒绝。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"name": "   "}, csrf_token=csrf_token,
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_update_rejects_non_string_value():
    """字段值为非字符串类型时被拒绝。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"name": 12345}, csrf_token=csrf_token,
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "A" * 51),
        ("phone", "1" * 21),
        ("major_class", "B" * 101),
        ("grade", "C" * 21),
    ],
)
def test_update_rejects_exceeding_max_length(field, value):
    """字段值超过最大长度时返回 VALIDATION_ERROR。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {field: value}, csrf_token=csrf_token,
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "VALIDATION_ERROR"


# ─── 权限与认证 ────────────────────────────────────────────


@pytest.mark.django_db
def test_update_rejects_unauthenticated():
    """未登录用户即使携带有效 CSRF 令牌也被拒绝（401）。"""
    client, token = csrf_client()

    response = patch_json(
        client, PROFILE_URL, {"name": "test"}, csrf_token=token,
    )

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_update_rejects_disabled_account():
    """已停用账号即使携带有效 CSRF 令牌也被拒绝（403）。"""
    user = create_student(
        username="disabled_student",
        account_status=get_user_model().AccountStatus.DISABLED,
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"name": "test"}, csrf_token=csrf_token,
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "ACCOUNT_DISABLED"


@pytest.mark.django_db
def test_update_rejects_admin_account():
    """系统管理员不能修改学生资料（403）。"""
    user = create_student(
        username="admin_user",
        platform_role=get_user_model().PlatformRole.ADMIN,
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"name": "test"}, csrf_token=csrf_token,
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


# ─── CSRF ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_update_rejects_missing_csrf():
    """缺少 CSRF 令牌时被拒绝。"""
    client = Client(enforce_csrf_checks=True)
    create_student(username="csrf_test_student")
    # 登录建立会话
    client.get(CSRF_URL)
    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({
            "username": "csrf_test_student",
            "password": "StrongPass!2026",
        }),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=response_body(client.get(CSRF_URL))["data"]["csrf_token"],
    )
    assert login_resp.status_code == 200

    # 不带 CSRF 令牌发送 PATCH
    response = client.patch(
        PROFILE_URL,
        data=json.dumps({"name": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "CSRF_FAILED"


# ─── 响应完整性 ────────────────────────────────────────────


@pytest.mark.django_db
def test_update_response_excludes_password():
    """响应不包含密码或密码哈希。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"name": "新名字"}, csrf_token=csrf_token,
    )

    body_str = json.dumps(response_body(response))
    assert "password" not in body_str


@pytest.mark.django_db
def test_update_response_contains_all_fields():
    """响应包含完整的 SelfUser 字段。"""
    client, _ = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]

    response = patch_json(
        client, PROFILE_URL, {"name": "完整字段测试"}, csrf_token=csrf_token,
    )

    data = response_body(response)["data"]
    assert set(data.keys()) == {
        "id", "username", "platform_role", "account_status",
        "registered_at", "name", "phone", "major_class", "grade",
    }


@pytest.mark.django_db
def test_update_does_not_change_system_fields():
    """修改资料不影响用户名、角色、状态和注册时间。"""
    client, user = login_student()
    csrf_resp = client.get(CSRF_URL)
    csrf_token = response_body(csrf_resp)["data"]["csrf_token"]
    original_username = user.username
    original_role = user.platform_role
    original_status = user.account_status
    original_registered_at = user.registered_at

    response = patch_json(
        client,
        PROFILE_URL,
        {"name": "修改后姓名", "phone": "13888888888"},
        csrf_token=csrf_token,
    )

    body = response_body(response)
    assert body["data"]["username"] == original_username
    assert body["data"]["platform_role"] == original_role
    assert body["data"]["account_status"] == original_status
    user.refresh_from_db()
    assert user.username == original_username
    assert user.platform_role == original_role
    assert user.account_status == original_status
    assert user.registered_at == original_registered_at
