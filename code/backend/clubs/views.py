import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_GET, require_POST

from core.exceptions import ApiError
from core.responses import success_response

from .models import Club, ClubMembership
from .serializers import (
    serialize_club,
    serialize_membership_for_admin,
    serialize_my_membership,
)


# ── 守卫函数 ────────────────────────────────────────────────

#要求用户已认证且为系统管理员，通过则返回 user 对象。
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


#要求用户已认证，且为学生（账号正常）或系统管理员，通过则返回 user 对象。
def require_student_or_admin(request):
    if not request.user.is_authenticated:
        raise ApiError(
            code="UNAUTHENTICATED",
            message="请先登录",
            status=401,
        )

    user_model = get_user_model()
    user = request.user

    if user.platform_role == user_model.PlatformRole.ADMIN:
        return user

    if user.platform_role != user_model.PlatformRole.STUDENT:
        raise ApiError(
            code="FORBIDDEN",
            message="当前账号无权执行此操作",
            status=403,
        )

    if user.account_status != user_model.AccountStatus.ACTIVE:
        raise ApiError(
            code="ACCOUNT_DISABLED",
            message="账号已停用",
            status=403,
        )

    return user


#要求用户已登录、账号启用且为学生角色，通过则返回 user 对象。
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


# ── 分页辅助 ────────────────────────────────────────────────

#默认分页参数
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

#解析并校验分页参数，返回 (page, page_size)。
def parse_pagination(request):
    try:
        page = int(request.GET.get("page", DEFAULT_PAGE))
        page_size = int(request.GET.get("page_size", DEFAULT_PAGE_SIZE))
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
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ApiError(
            code="VALIDATION_ERROR",
            message=f"每页条数必须在 1—{MAX_PAGE_SIZE} 之间",
            status=422,
        )

    return page, page_size


#对 QuerySet 执行分页切片并返回 (items, total)。
def paginate(queryset, page, page_size):
    total = queryset.count()
    offset = (page - 1) * page_size
    items = list(queryset[offset : offset + page_size])
    return items, total


#构建分页响应 data。
def paginated_response(items, page, page_size, total):
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


# ── 社团类别校验 ────────────────────────────────────────────

VALID_CATEGORIES = {
    choice.value for choice in Club.Category
}


# ── Logo 保存 ────────────────────────────────────────────────

#接受上传文件对象，保存到 media/logos/ 并返回相对路径。
def save_logo(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1] or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    from django.conf import settings

    logos_dir = settings.MEDIA_ROOT / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    filepath = logos_dir / filename

    with open(filepath, "wb") as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    return f"logos/{filename}"


# ── POST /api/admin/clubs ────────────────────────────────────

#创建社团允许的文本字段
CREATE_CLUB_TEXT_FIELDS = {"name", "category", "introduction"}

#校验社团类别是否合法。
def validate_category(category):
    if category not in VALID_CATEGORIES:
        raise ApiError(
            code="INVALID_CLUB_CATEGORY",
            message=f"社团类别必须是以下之一：{'、'.join(sorted(VALID_CATEGORIES))}",
            status=422,
        )


#解析并校验 leader_user_ids JSON 字符串，返回去重后的整数列表。
#负责人必须至少一名，不能重复，且均为账号正常的学生。
def parse_leader_user_ids(raw_value):
    if not raw_value:
        raise ApiError(
            code="INITIAL_LEADER_REQUIRED",
            message="至少需要指定一名初始负责人",
            status=400,
        )

    try:
        ids = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        raise ApiError(
            code="INVALID_REQUEST",
            message="负责人 ID 列表格式不正确",
            status=400,
        )

    if not isinstance(ids, list) or len(ids) == 0:
        raise ApiError(
            code="INITIAL_LEADER_REQUIRED",
            message="至少需要指定一名初始负责人",
            status=400,
        )

    #类型校验
    if not all(isinstance(i, int) for i in ids):
        raise ApiError(
            code="INVALID_REQUEST",
            message="负责人 ID 必须是整数",
            status=400,
        )

    #去重
    unique_ids = list(dict.fromkeys(ids))
    if len(unique_ids) != len(ids):
        raise ApiError(
            code="INVALID_REQUEST",
            message="负责人 ID 列表包含重复值",
            status=400,
        )

    return unique_ids


#校验初始负责人是否均为账号正常的学生。
def validate_initial_leaders(leader_ids):
    user_model = get_user_model()
    users = list(
        user_model.objects.filter(
            id__in=leader_ids,
            platform_role=user_model.PlatformRole.STUDENT,
            account_status=user_model.AccountStatus.ACTIVE,
        )
    )

    if len(users) != len(leader_ids):
        #找出无效的 ID
        valid_ids = {u.id for u in users}
        invalid_ids = [i for i in leader_ids if i not in valid_ids]
        raise ApiError(
            code="INITIAL_LEADER_INVALID",
            message=f"以下负责人 ID 无效或不是正常学生账号：{', '.join(str(i) for i in invalid_ids)}",
            status=422,
        )

    return users


#POST /api/admin/clubs — 管理员创建社团并指定初始负责人。
def _admin_create_club(request):
    require_admin(request)

    #校验 Content-Type 为 multipart/form-data
    content_type = request.content_type or ""
    if not content_type.startswith("multipart/form-data"):
        raise ApiError(
            code="INVALID_REQUEST",
            message="创建社团需使用 multipart/form-data",
            status=400,
        )

    #解析文本字段
    name = (request.POST.get("name") or "").strip()
    category = (request.POST.get("category") or "").strip()
    introduction = (request.POST.get("introduction") or "").strip()
    leader_user_ids_raw = (request.POST.get("leader_user_ids") or "").strip()

    #必填字段校验
    if not name:
        raise ApiError(
            code="INVALID_REQUEST",
            message="社团名称不能为空",
            status=400,
        )
    if len(name) > 100:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="社团名称超过允许长度",
            status=422,
        )
    if not category:
        raise ApiError(
            code="INVALID_REQUEST",
            message="社团类别不能为空",
            status=400,
        )
    validate_category(category)
    if not introduction:
        raise ApiError(
            code="INVALID_REQUEST",
            message="社团简介不能为空",
            status=400,
        )

    #Logo 必填
    uploaded_file = request.FILES.get("logo")
    if not uploaded_file:
        raise ApiError(
            code="LOGO_REQUIRED",
            message="社团 Logo 为必填项",
            status=400,
        )

    #解析 leader_user_ids
    leader_ids = parse_leader_user_ids(leader_user_ids_raw)
    leaders = validate_initial_leaders(leader_ids)

    #重名检查
    if Club.objects.filter(name=name).exists():
        raise ApiError(
            code="CLUB_NAME_EXISTS",
            message="社团名称已存在",
            status=409,
        )

    #在事务中创建社团和初始成员关系
    try:
        with transaction.atomic():
            #保存 Logo
            logo_path = save_logo(uploaded_file)

            #创建社团
            club = Club.objects.create(
                name=name,
                category=category,
                introduction=introduction,
                logo=logo_path,
            )

            #创建初始负责人成员关系
            memberships = []
            for leader in leaders:
                membership = ClubMembership.objects.create(
                    user=leader,
                    club=club,
                    member_status=ClubMembership.MemberStatus.ACTIVE,
                    club_role=ClubMembership.ClubRole.LEADER,
                )
                memberships.append(membership)

    except IntegrityError as error:
        raise ApiError(
            code="CLUB_NAME_EXISTS",
            message="社团名称已存在",
            status=409,
        ) from error

    return success_response(
        data={
            "club": serialize_club(club),
            "leaders": [serialize_membership_for_admin(m) for m in memberships],
        },
        message="社团创建成功",
        status=201,
    )


# ── GET /api/admin/clubs ─────────────────────────────────────

#GET /api/admin/clubs — 管理员查看全部社团（正常和已注销），分页。
def _admin_list_clubs(request):
    require_admin(request)
    page, page_size = parse_pagination(request)

    queryset = Club.objects.order_by("id")
    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_club(c) for c in items],
            page,
            page_size,
            total,
        ),
        message="社团列表获取成功",
    )


# /api/admin/clubs — 管理员社团管理入口，按方法分发。
def admin_clubs(request):
    if request.method == "POST":
        return _admin_create_club(request)
    if request.method == "GET":
        return _admin_list_clubs(request)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── GET /api/clubs ──────────────────────────────────────────

#GET /api/clubs — 公开社团列表（只返回正常社团），分页，可选按类别筛选。
@require_GET
def public_list_clubs(request):
    require_student_or_admin(request)
    page, page_size = parse_pagination(request)

    queryset = Club.objects.filter(status=Club.Status.ACTIVE)

    #可选类别筛选
    category_filter = (request.GET.get("category") or "").strip()
    if category_filter:
        validate_category(category_filter)
        queryset = queryset.filter(category=category_filter)

    queryset = queryset.order_by("id")
    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_club(c) for c in items],
            page,
            page_size,
            total,
        ),
        message="社团列表获取成功",
    )


# ── GET /api/clubs/{club_id} ─────────────────────────────────

#GET /api/clubs/{club_id} — 社团详情。
#学生只能查看正常社团（已注销返回 RESOURCE_NOT_FOUND）；管理员可查看任意状态。
@require_GET
def club_detail(request, club_id):
    user = require_student_or_admin(request)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    #非管理员只能看正常社团
    user_model = get_user_model()
    if user.platform_role != user_model.PlatformRole.ADMIN:
        if club.status != Club.Status.ACTIVE:
            raise ApiError(
                code="RESOURCE_NOT_FOUND",
                message="社团不存在",
                status=404,
            )

    return success_response(
        data=serialize_club(club),
        message="社团详情获取成功",
    )


# ── GET /api/me/memberships ──────────────────────────────────

#GET /api/me/memberships — 当前学生的全部成员关系（当前及历史）。
@require_GET
def my_memberships(request):
    user = require_active_student(request)

    memberships = ClubMembership.objects.filter(
        user=user,
    ).select_related("club").order_by("-id")

    return success_response(
        data={
            "items": [serialize_my_membership(m) for m in memberships],
        },
        message="我的社团获取成功",
    )
