from django.conf import settings
from django.contrib.auth import get_user_model


def test_custom_user_model_is_selected_before_first_migration():
    assert settings.AUTH_USER_MODEL == "users.User"


def test_user_model_matches_the_s00_contract():
    user_model = get_user_model()
    field_names = {field.name for field in user_model._meta.fields}

    assert user_model._meta.db_table == "user"
    assert {
        "id",
        "username",
        "password",
        "platform_role",
        "account_status",
        "registered_at",
        "name",
        "phone",
        "major_class",
        "grade",
    } == field_names
    assert user_model._meta.get_field("password").db_column == "password_hash"


def test_password_uses_django_secure_hashing():
    user_model = get_user_model()
    user = user_model(
        username="student",
        name="Student",
        phone="13800000000",
        major_class="Computer Science 1",
        grade="2026",
    )

    user.set_password("local-test-password")

    assert user.password != "local-test-password"
    assert user.check_password("local-test-password")


def test_user_defaults_to_active_student_without_club_role():
    user_model = get_user_model()
    user = user_model(
        username="student",
        name="Student",
        phone="13800000000",
        major_class="Computer Science 1",
        grade="2026",
    )

    assert user.platform_role == user_model.PlatformRole.STUDENT
    assert user.account_status == user_model.AccountStatus.ACTIVE
    assert not hasattr(user, "club_role")
