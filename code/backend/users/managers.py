
# 导入 Django 提供的用户管理器基类
from django.contrib.auth.base_user import BaseUserManager

## 自定义用户管理器，负责创建普通用户和超级用户
class UserManager(BaseUserManager):
    # 允许 Django 在数据库迁移文件中使用这个管理器
    use_in_migrations = True
    #创建用户
    def create_user(self, username, password=None, **extra_fields):
        #用户名不能为空
        if not username:
            raise ValueError("用户名不能为空")


        #用户对象
        user = self.model(
            #把用户名做标准化处理。特殊字符会被转换成统一形式，避免“看起来一样、实际不同”的用户名
            username=self.model.normalize_username(username),
            **extra_fields,
        )
        #加密密码并存到数据库
        user.set_password(password)
        user.save(using=self._db)
        return user


    #创建管理员用户
    def create_superuser(self, username, password=None, **extra_fields):
        #导入我自定义的User模型
        from .models import User
        #如果调用者没有提供 platform_role，自动设置为：系统管理员。
        extra_fields.setdefault("platform_role", User.PlatformRole.ADMIN)

        #如果没有提供账户状态，默认设置为：可用
        extra_fields.setdefault("account_status", User.AccountStatus.ACTIVE)

        #进行安全检查：如果有人试图创建一个平台角色不是管理员的“超级用户”，直接报错。
        if extra_fields["platform_role"] != User.PlatformRole.ADMIN:
            raise ValueError("超级用户的平台角色必须是系统管理员")

        return self.create_user(username, password, **extra_fields)
