import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
PROFILE_URL = "/api/me/profile"

VALID_REGISTRATION = {
    "username": "student_2026",
    "password": "StrongPass!2026",
    "name": "张同学",
    "phone": "13800000000",
    "major_class": "计算机科学与技术1班",
    "grade": "2026",
}


def response_body(response):
    return json.loads(response.content)


def post_json(client, url, data):
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


def create_user(**overrides):
    data = {
        "username": "existing_student",
        "password": "StrongPass!2026",
        "name": "李同学",
        "phone": "13900000000",
        "major_class": "软件工程1班",
        "grade": "2025",
    }
    data.update(overrides)
    return get_user_model().objects.create_user(**data)


@pytest.mark.django_db
def test_registration_creates_active_student_without_logging_in():
    client = Client()

    response = post_json(client, REGISTER_URL, VALID_REGISTRATION)

    assert response.status_code == 201
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["username"] == VALID_REGISTRATION["username"]
    assert body["data"]["platform_role"] == "student"
    assert body["data"]["account_status"] == "active"
    assert "password" not in json.dumps(body)

    user = get_user_model().objects.get(
        username=VALID_REGISTRATION["username"],
    )
    assert user.platform_role == user.PlatformRole.STUDENT
    assert user.account_status == user.AccountStatus.ACTIVE
    assert user.password != VALID_REGISTRATION["password"]
    assert user.check_password(VALID_REGISTRATION["password"])

    profile_response = client.get(PROFILE_URL)
    assert profile_response.status_code == 401
    assert response_body(profile_response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_registration_rejects_duplicate_username():
    create_user(username=VALID_REGISTRATION["username"])
    client = Client()

    response = post_json(client, REGISTER_URL, VALID_REGISTRATION)

    assert response.status_code == 409
    assert response_body(response)["code"] == "USERNAME_EXISTS"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("platform_role", "system_admin"),
        ("account_status", "disabled"),
        ("registered_at", "2026-07-29T10:00:00+08:00"),
    ],
)
def test_registration_rejects_client_controlled_system_fields(field, value):
    client = Client()
    payload = {**VALID_REGISTRATION, field: value}

    response = post_json(client, REGISTER_URL, payload)

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"
    assert not get_user_model().objects.filter(
        username=VALID_REGISTRATION["username"],
    ).exists()


@pytest.mark.django_db
def test_registration_applies_django_password_validation():
    client = Client()
    payload = {**VALID_REGISTRATION, "password": "12345678"}

    response = post_json(client, REGISTER_URL, payload)

    assert response.status_code == 422
    assert response_body(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_login_sets_httponly_session_and_profile_reads_session_user():
    user = create_user()
    client = Client()

    response = post_json(
        client,
        LOGIN_URL,
        {"username": user.username, "password": "StrongPass!2026"},
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["id"] == user.id
    assert "sessionid" in response.cookies
    assert response.cookies["sessionid"]["httponly"] is True

    profile_response = client.get(PROFILE_URL)
    assert profile_response.status_code == 200
    profile = response_body(profile_response)["data"]
    assert profile == response_body(response)["data"]
    assert profile["phone"] == user.phone
    assert "password" not in json.dumps(profile)


@pytest.mark.django_db
def test_login_rejects_invalid_credentials():
    create_user()
    client = Client()

    response = post_json(
        client,
        LOGIN_URL,
        {"username": "existing_student", "password": "WrongPass!2026"},
    )

    assert response.status_code == 401
    assert response_body(response)["code"] == "INVALID_CREDENTIALS"
    assert "sessionid" not in response.cookies


@pytest.mark.django_db
def test_login_rejects_disabled_account():
    create_user(account_status=get_user_model().AccountStatus.DISABLED)
    client = Client()

    response = post_json(
        client,
        LOGIN_URL,
        {
            "username": "existing_student",
            "password": "StrongPass!2026",
        },
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "ACCOUNT_DISABLED"


@pytest.mark.django_db
def test_profile_rejects_anonymous_user():
    response = Client().get(PROFILE_URL)

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_profile_rejects_disabled_existing_session():
    user = create_user(
        account_status=get_user_model().AccountStatus.DISABLED,
    )
    client = Client()
    client.force_login(user)

    response = client.get(PROFILE_URL)

    assert response.status_code == 403
    assert response_body(response)["code"] == "ACCOUNT_DISABLED"


@pytest.mark.django_db
def test_profile_rejects_system_admin():
    user = create_user(
        username="admin",
        platform_role=get_user_model().PlatformRole.ADMIN,
    )
    client = Client()
    client.force_login(user)

    response = client.get(PROFILE_URL)

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"
