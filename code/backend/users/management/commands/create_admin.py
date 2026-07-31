from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "创建系统管理员账号，用于受控初始化。不提供公开管理员注册。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help="管理员用户名（全局唯一）",
        )
        parser.add_argument(
            "--password",
            required=True,
            help="管理员密码（需通过 Django 密码强度校验）",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        user_model = get_user_model()

        # 检查用户名是否已存在
        if user_model.objects.filter(username=username).exists():
            raise CommandError(f"用户名 '{username}' 已存在，请更换用户名。")

        # 校验密码强度（复用 Django 默认密码校验器）
        candidate = user_model(username=username)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError("；".join(error.messages)) from error

        # 创建管理员账号
        user = user_model.objects.create_user(
            username=username,
            password=password,
            name="系统管理员",
            phone="",
            major_class="",
            grade="",
            platform_role=user_model.PlatformRole.ADMIN,
            account_status=user_model.AccountStatus.ACTIVE,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"系统管理员 '{user.username}'（id={user.id}）已创建。"
            )
        )
