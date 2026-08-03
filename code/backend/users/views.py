import json

from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_GET, require_POST

from core.exceptions import ApiError
from core.responses import success_response

from .serializers import serialize_admin_student, serialize_self_user

#请求字段配置
#注册字段
REGISTER_FIELDS = {
    "username",
    "password",
    "name",
    "phone",
    "major_class",
    "grade",
}
#登录字段
LOGIN_FIELDS = {"username", "password"}

#各字段最大长度限制，用于防止超长输入
FIELD_MAX_LENGTHS = {
    "username": 150,
    "name": 50,
    "phone": 20,
    "major_class": 100,
    "grade": 20,
}

#公共检查函数
def parse_json_object(request, expected_fields):
    #校验 Content-Type
    if request.content_type != "application/json":
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体必须使用 JSON",
            status=400,
        )
    #校验 JSON 可解析性
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体不是有效的 JSON",
            status=400,
        )
    #白名单字段校验：必须是 dict，且字段集合恰好等于 expected_fields
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段缺失或包含不允许的字段",
            status=400,
        )
    # 类型校验：所有字段值必须是字符串
    if any(not isinstance(payload[field], str) for field in expected_fields):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段必须为字符串",
            status=400,
        )
    #去除首尾空白（密码字段除外，因为密码中的空格可能是用户有意输入的）
    for field in expected_fields - {"password"}:
        payload[field] = payload[field].strip()
    # 非空校验：去空白后不能为空
    if any(not payload[field] for field in expected_fields):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段不能为空",
            status=400,
        )
    #长度校验
    for field, maximum in FIELD_MAX_LENGTHS.items():
        if field in payload and len(payload[field]) > maximum:
            raise ApiError(
                code="VALIDATION_ERROR",
                message=f"{field} 超过允许长度",
                status=422,
            )

    return payload

#要求当前用户是未登录状态
#如果已登录，直接抛出403阻止操作
def require_anonymous(request):
    if request.user.is_authenticated:
        raise ApiError(
            code="FORBIDDEN",
            message="已登录用户不能执行此操作",
            status=403,
        )

#守卫：要求用户已登录、账号启用且为学生角色，通过则返回 user 对象。
#检查身份→要么报错、要么放行并返回用户
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


#守卫：要求用户已认证且为系统管理员，通过则返回 user 对象。
def require_admin(request):
    if not request.user.is_authenticated:
        raise ApiError(
            code="UNAUTHENTICATED",
            message="请先登录",
            status=401,
        )

    user_model = get_user_model()
    if request.user.platform_role != user_model.PlatformRole.ADMIN:
        raise ApiError(
            code="FORBIDDEN",
            message="当前账号不是管理员账号",
            status=403,
        )

    return request.user


#POST /api/auth/register — 学生注册，校验字段与密码强度后创建用户。
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

#POST /api/auth/login — 学生登录，凭据校验通过后创建 Session。
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

#本人资料相关 — 获取与修改

#本人资料允许学生自行修改的字段
PROFILE_EDITABLE_FIELDS = {"name", "phone", "major_class", "grade"}

#GET /api/me/profile — 返回当前登录学生的个人资料。
#PATCH /api/me/profile — 修改本人可维护资料，至少提交一个字段。
def profile(request):
    if request.method == "PATCH":
        return _profile_update(request)

    user = require_active_student(request)
    return success_response(
        data=serialize_self_user(user),
        message="本人资料获取成功",
    )


#PATCH /api/me/profile — 修改本人姓名、手机号、专业班级、年级。
#校验权限、字段白名单、类型、非空和长度后更新入库。
def _profile_update(request):
    user = require_active_student(request)
    payload = _safe_parse_body(request)

    #校验 JSON 对象类型
    if not isinstance(payload, dict):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体必须为 JSON 对象",
            status=400,
        )

    #白名单字段校验：只允许可编辑字段，且至少提交一个
    submitted_fields = set(payload.keys())
    if not submitted_fields:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请至少提供一个要修改的字段",
            status=400,
        )
    if not submitted_fields.issubset(PROFILE_EDITABLE_FIELDS):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求包含不允许修改的字段",
            status=400,
        )

    #类型校验：所有字段值必须是字符串
    if any(not isinstance(payload[field], str) for field in submitted_fields):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段必须为字符串",
            status=400,
        )

    #去除首尾空白
    for field in submitted_fields:
        payload[field] = payload[field].strip()

    #非空校验：去空白后不能为空
    if any(not payload[field] for field in submitted_fields):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段不能为空",
            status=400,
        )

    #长度校验
    for field in submitted_fields:
        maximum = FIELD_MAX_LENGTHS.get(field)
        if maximum and len(payload[field]) > maximum:
            raise ApiError(
                code="VALIDATION_ERROR",
                message=f"{field} 超过允许长度",
                status=422,
            )

    #应用更新，只更新提交的字段
    for field in submitted_fields:
        setattr(user, field, payload[field])
    user.save(update_fields=list(submitted_fields))

    return success_response(
        data=serialize_self_user(user),
        message="资料修改成功",
    )


#安全解析 JSON 请求体，仅校验格式，不做字段约束。
#返回 dict 或在格式错误时抛出 ApiError。
def _safe_parse_body(request):
    #校验 Content-Type
    if request.content_type != "application/json":
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体必须使用 JSON",
            status=400,
        )
    #校验 JSON 可解析性
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体不是有效的 JSON",
            status=400,
        )


# ── 管理员用户管理 ────────────────────────────────────────────

#管理员用户列表分页默认参数
ADMIN_USERS_DEFAULT_PAGE = 1
ADMIN_USERS_DEFAULT_PAGE_SIZE = 20
ADMIN_USERS_MAX_PAGE_SIZE = 100

#GET /api/admin/users — 管理员分页查看学生账号列表，不含管理员账号。
@require_GET
def admin_list_users(request):
    admin = require_admin(request)
    user_model = get_user_model()

    # 解析分页参数
    try:
        page = int(request.GET.get("page", ADMIN_USERS_DEFAULT_PAGE))
        page_size = int(request.GET.get("page_size", ADMIN_USERS_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        raise ApiError(
            code="VALIDATION_ERROR",
            message="分页参数必须为整数",
            status=422,
        )

    if page < 1:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="页码必须大于等于 1",
            status=422,
        )
    if page_size < 1 or page_size > ADMIN_USERS_MAX_PAGE_SIZE:
        raise ApiError(
            code="VALIDATION_ERROR",
            message=f"每页条数必须在 1—{ADMIN_USERS_MAX_PAGE_SIZE} 之间",
            status=422,
        )

    # 只查询学生用户
    queryset = user_model.objects.filter(
        platform_role=user_model.PlatformRole.STUDENT,
    ).order_by("id")

    total = queryset.count()
    offset = (page - 1) * page_size
    users = list(queryset[offset : offset + page_size])

    return success_response(
        data={
            "items": [serialize_admin_student(u) for u in users],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        message="学生用户列表获取成功",
    )


#POST /api/admin/users/{user_id}/reset-password — 管理员重置学生密码。
@require_POST
def admin_reset_password(request, user_id):
    admin = require_admin(request)
    user_model = get_user_model()

    # 查找目标用户
    try:
        target_user = user_model.objects.get(id=user_id)
    except user_model.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="用户不存在",
            status=404,
        )

    # 只能为学生重置密码
    if target_user.platform_role != user_model.PlatformRole.STUDENT:
        raise ApiError(
            code="NOT_STUDENT_USER",
            message="只能为学生账号重置密码",
            status=422,
        )

    # 解析请求体
    payload = _safe_parse_body(request)
    if not isinstance(payload, dict) or set(payload) != {"new_password"}:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段缺失或包含不允许的字段",
            status=400,
        )

    new_password = payload["new_password"]
    if not isinstance(new_password, str) or not new_password.strip():
        raise ApiError(
            code="INVALID_REQUEST",
            message="新密码不能为空",
            status=400,
        )

    # 校验密码强度
    try:
        validate_password(new_password, user=target_user)
    except ValidationError as error:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="；".join(error.messages),
            status=422,
        ) from error

    # 设置新密码
    target_user.set_password(new_password)
    target_user.save(update_fields=["password"])

    return success_response(
        data={"user_id": target_user.id},
        message="密码重置成功",
    )


# ── S20：管理员停用/恢复学生账号 ────────────────────────────────

#允许的目标状态值
ALLOWED_ACCOUNT_STATUSES = {"active", "disabled"}


#统计目标学生作为有效负责人的正常社团数量（排除该学生本人后）。
def _count_other_effective_leaders(club, exclude_user):
    """返回 club 中除 exclude_user 外的有效负责人数量。"""
    from clubs.models import ClubMembership

    user_model = get_user_model()
    return ClubMembership.objects.filter(
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club_role=ClubMembership.ClubRole.LEADER,
        user__account_status=user_model.AccountStatus.ACTIVE,
    ).exclude(user=exclude_user).count()


#PATCH /api/admin/users/{user_id}/status — 管理员停用或恢复学生账号。
def admin_update_user_status(request, user_id):
    if request.method != "PATCH":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )
    require_admin(request)
    user_model = get_user_model()

    # 查找目标用户
    try:
        target_user = user_model.objects.get(id=user_id)
    except user_model.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="用户不存在",
            status=404,
        )

    # 只能操作学生账号
    if target_user.platform_role != user_model.PlatformRole.STUDENT:
        raise ApiError(
            code="NOT_STUDENT_USER",
            message="只能操作学生账号",
            status=422,
        )

    # 解析请求体，严格校验字段
    payload = _safe_parse_body(request)
    if not isinstance(payload, dict) or set(payload) != {"account_status"}:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求字段缺失或包含不允许的字段",
            status=400,
        )

    new_status = payload["account_status"]
    if not isinstance(new_status, str) or new_status not in ALLOWED_ACCOUNT_STATUSES:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="account_status 必须为 active 或 disabled",
            status=422,
        )

    # 未实际变更时直接返回成功
    if target_user.account_status == new_status:
        return success_response(
            data={"user_id": target_user.id, "account_status": target_user.account_status},
            message="账号状态未变更",
        )

    # 停用前检查最后有效负责人保护
    if new_status == user_model.AccountStatus.DISABLED:
        from clubs.models import Club, ClubMembership

        # 查询该学生作为有效负责人的所有正常社团
        leader_memberships = ClubMembership.objects.filter(
            user=target_user,
            member_status=ClubMembership.MemberStatus.ACTIVE,
            club_role=ClubMembership.ClubRole.LEADER,
            club__status=Club.Status.ACTIVE,
        ).select_related("club")

        for membership in leader_memberships:
            if _count_other_effective_leaders(membership.club, target_user) == 0:
                raise ApiError(
                    code="LAST_EFFECTIVE_LEADER",
                    message=f"不能停用该学生：社团「{membership.club.name}」将失去最后一名有效负责人",
                    status=409,
                )

    # 执行状态变更
    target_user.account_status = new_status
    target_user.save(update_fields=["account_status"])

    action_label = "已停用" if new_status == user_model.AccountStatus.DISABLED else "已恢复"
    return success_response(
        data={"user_id": target_user.id, "account_status": target_user.account_status},
        message=f"学生账号{action_label}",
    )
