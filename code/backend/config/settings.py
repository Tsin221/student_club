import os
from pathlib import Path

from dotenv import load_dotenv

#基础路径与环境变量
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent

load_dotenv(PROJECT_DIR / ".env")

#将逗号分隔的环境变量转换为列表。
def env_list(name):
    return [
        value.strip()
        for value in os.environ.get(name, "").split(",")
        if value.strip()
    ]

#Django 基础配置
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

#应用配置
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "core",
    "users",
    "clubs",
]

#中间件配置
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.ApiExceptionMiddleware",
]


#路由与服务入口
ROOT_URLCONF = "config.urls"

TEMPLATES = []

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

#数据库配置
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ["MYSQL_DATABASE"],
        "USER": os.environ["MYSQL_USER"],
        "PASSWORD": os.environ["MYSQL_PASSWORD"],
        "HOST": os.environ["MYSQL_HOST"],
        "PORT": os.environ["MYSQL_PORT"],
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


#用户与密码配置
AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS = ["users.backends.SessionUserBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]

#语言与时区配置
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

#Session 配置
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG

#模型默认配置
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

#媒体文件配置（Logo 上传）
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── DeepSeek AI 配置 ─────────────────────────────────────────

DEEPSEEK_API_URL = os.environ.get(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions",
)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
# AI 单次请求允许的最大内容字符数（用于截断）
AI_MAX_CONTENT_CHARS = int(os.environ.get("AI_MAX_CONTENT_CHARS", "8000"))
