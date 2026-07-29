from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from .managers import UserManager

#用户模型
class User(AbstractBaseUser):


    #用来确定是系统管理员还是学生
    class PlatformRole(models.TextChoices):
        ADMIN = "system_admin", "系统管理员"
        STUDENT = "student", "学生用户"


    #账号状态
    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "正常"
        DISABLED = "disabled", "已停用"


    #用户基础字段: id,用户名,密码
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(
        max_length=255,
        db_column="password_hash",
    )


    #------用户权限与状态字段--------
    #用户在平台的角色
    platform_role = models.CharField(
        max_length=20,
        choices=PlatformRole.choices,
        default=PlatformRole.STUDENT,
    )

    #用户的账号状态
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )

    #---------用户个人信息-----------
    #注册时间，真实姓名，电话，专业班级，年级
    registered_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    major_class = models.CharField(max_length=100)
    grade = models.CharField(max_length=20)

    #登录时间设置
    last_login = None

    #自定义用户管理器
    objects = UserManager()


    #----------Django 认证配置----------------
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name", "phone", "major_class", "grade"]



    #-------数据库配置---------
    class Meta:
        db_table = "user"
        indexes = [
            models.Index(
                fields=["platform_role", "account_status"],
                name="user_role_status_idx",
            )
        ]


    #-----------用户状态属性---------------

    #检查用户是否可用
    @property
    def is_active(self):
        return self.account_status == self.AccountStatus.ACTIVE

    #检查用户是否可以访问后台
    @property
    def is_staff(self):
        return self.platform_role == self.PlatformRole.ADMIN

    #判断用户是否拥有系统超级管理员权限。
    @property
    def is_superuser(self):
        return self.platform_role == self.PlatformRole.ADMIN


    #判断是否拥有某个具体权限
    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser


    #判断用户是否拥有访问某个 Django 应用模块的权限。
    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser


    #获取完整用户名
    def get_full_name(self):
        return self.name


    #获取用户简称
    def get_short_name(self):
        return self.name


    #字符串显示
    def __str__(self):
        return self.username
