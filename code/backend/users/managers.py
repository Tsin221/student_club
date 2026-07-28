from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("用户名不能为空")

        user = self.model(
            username=self.model.normalize_username(username),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        from .models import User

        extra_fields.setdefault("platform_role", User.PlatformRole.ADMIN)
        extra_fields.setdefault("account_status", User.AccountStatus.ACTIVE)

        if extra_fields["platform_role"] != User.PlatformRole.ADMIN:
            raise ValueError("超级用户的平台角色必须是系统管理员")

        return self.create_user(username, password, **extra_fields)
