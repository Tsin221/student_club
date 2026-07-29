import json

from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from core.exceptions import ApiError
from core.responses import success_response

from .serializers import serialize_self_user


REGISTER_FIELDS = {
    "username",
    "password",
    "name",
    "phone",
    "major_class",
    "grade",
}
LOGIN_FIELDS = {"username", "password"}
FIELD_MAX_LENGTHS = {
    "username": 150,
    "name": 50,
    "phone": 20,
    "major_class": 100,
    "grade": 20,
}


def parse_json_object(request, expected_fields):
    if request.content_type != "application/json":
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体必须使用 JSON",
            status=400,
        )

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体不是有效的 JSON",
            status=400,
        )

    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段缺失或包含不允许的字段",
            status=400,
        )

    if any(not isinstance(payload[field], str) for field in expected_fields):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段必须为字符串",
            status=400,
        )

    for field in expected_fields - {"password"}:
        payload[field] = payload[field].strip()

    if any(not payload[field] for field in expected_fields):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段不能为空",
            status=400,
        )

    for field, maximum in FIELD_MAX_LENGTHS.items():
        if field in payload and len(payload[field]) > maximum:
            raise ApiError(
                code="VALIDATION_ERROR",
                message=f"{field} 超过允许长度",
                status=422,
            )

    return payload


def require_anonymous(request):
    if request.user.is_authenticated:
        raise ApiError(
            code="FORBIDDEN",
            message="已登录用户不能执行此操作",
            status=403,
        )


def require_active_student(request):
    if not request.user.is_authenticated:
        raise ApiError(
            code="UNAUTHENTICATED",
            message="请先登录",
            status=401,
        )

    user_model = get_user_model()
    if request.user.account_status != user_model.AccountStatus.ACTIVE:
        raise ApiError(
            code="ACCOUNT_DISABLED",
            message="账号已停用",
            status=403,
        )

    if request.user.platform_role != user_model.PlatformRole.STUDENT:
        raise ApiError(
            code="FORBIDDEN",
            message="当前账号不是学生账号",
            status=403,
        )

    return request.user


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return success_response(
        data={"csrf_token": get_token(request)},
        message="CSRF 令牌初始化成功",
    )


@require_POST
def register(request):
    require_anonymous(request)
    payload = parse_json_object(request, REGISTER_FIELDS)
    user_model = get_user_model()

    if user_model.objects.filter(username=payload["username"]).exists():
        raise ApiError(
            code="USERNAME_EXISTS",
            message="用户名已存在",
            status=409,
        )

    candidate = user_model(
        username=payload["username"],
        name=payload["name"],
        phone=payload["phone"],
        major_class=payload["major_class"],
        grade=payload["grade"],
        platform_role=user_model.PlatformRole.STUDENT,
        account_status=user_model.AccountStatus.ACTIVE,
    )
    try:
        validate_password(payload["password"], user=candidate)
    except ValidationError as error:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="；".join(error.messages),
            status=422,
        ) from error

    try:
        with transaction.atomic():
            user = user_model.objects.create_user(
                username=payload["username"],
                password=payload["password"],
                name=payload["name"],
                phone=payload["phone"],
                major_class=payload["major_class"],
                grade=payload["grade"],
                platform_role=user_model.PlatformRole.STUDENT,
                account_status=user_model.AccountStatus.ACTIVE,
            )
    except IntegrityError as error:
        raise ApiError(
            code="USERNAME_EXISTS",
            message="用户名已存在",
            status=409,
        ) from error

    return success_response(
        data=serialize_self_user(user),
        message="注册成功，请登录",
        status=201,
    )


@require_POST
def login_view(request):
    require_anonymous(request)
    payload = parse_json_object(request, LOGIN_FIELDS)
    user_model = get_user_model()

    try:
        user = user_model.objects.get(username=payload["username"])
    except user_model.DoesNotExist:
        user = None

    if user is None:
        user_model().set_password(payload["password"])
    if user is None or not user.check_password(payload["password"]):
        raise ApiError(
            code="INVALID_CREDENTIALS",
            message="用户名或密码错误",
            status=401,
        )

    if user.account_status != user_model.AccountStatus.ACTIVE:
        raise ApiError(
            code="ACCOUNT_DISABLED",
            message="账号已停用",
            status=403,
        )

    login(
        request,
        user,
        backend="users.backends.SessionUserBackend",
    )
    return success_response(
        data=serialize_self_user(user),
        message="登录成功",
    )


@require_GET
def profile(request):
    user = require_active_student(request)
    return success_response(
        data=serialize_self_user(user),
        message="本人资料获取成功",
    )
