from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser):
    class PlatformRole(models.TextChoices):
        ADMIN = "system_admin", "系统管理员"
        STUDENT = "student", "学生用户"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "正常"
        DISABLED = "disabled", "已停用"

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(
        max_length=255,
        db_column="password_hash",
    )
    platform_role = models.CharField(
        max_length=20,
        choices=PlatformRole.choices,
        default=PlatformRole.STUDENT,
    )
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    major_class = models.CharField(max_length=100)
    grade = models.CharField(max_length=20)
    last_login = None

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name", "phone", "major_class", "grade"]

    class Meta:
        db_table = "user"
        indexes = [
            models.Index(
                fields=["platform_role", "account_status"],
                name="user_role_status_idx",
            )
        ]

    @property
    def is_active(self):
        return self.account_status == self.AccountStatus.ACTIVE

    @property
    def is_staff(self):
        return self.platform_role == self.PlatformRole.ADMIN

    @property
    def is_superuser(self):
        return self.platform_role == self.PlatformRole.ADMIN

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __str__(self):
        return self.username
