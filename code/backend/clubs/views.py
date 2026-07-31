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
    serialize_membership_for_leader,
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


#要求用户是目标社团当前有效负责人（账号正常、社团正常、在社、负责人）。
#通过则返回 (user, membership)。
def require_leader_of_club(request, club_id):
    if not request.user.is_authenticated:
        raise ApiError(
            code="UNAUTHENTICATED",
            message="请先登录",
            status=401,
        )

    user_model = get_user_model()
    user = request.user

    if user.platform_role != user_model.PlatformRole.STUDENT:
        raise ApiError(
            code="FORBIDDEN",
            message="当前账号不是学生账号",
            status=403,
        )

    if user.account_status != user_model.AccountStatus.ACTIVE:
        raise ApiError(
            code="ACCOUNT_DISABLED",
            message="账号已停用",
            status=403,
        )

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    if club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="社团已注销，当前操作不可用",
            status=409,
        )

    try:
        membership = ClubMembership.objects.get(user=user, club=club)
    except ClubMembership.DoesNotExist:
        raise ApiError(
            code="NOT_CLUB_LEADER",
            message="你不是该社团的负责人",
            status=403,
        )

    if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
        raise ApiError(
            code="NOT_CLUB_LEADER",
            message="你不是该社团的当前有效负责人",
            status=403,
        )

    if membership.club_role != ClubMembership.ClubRole.LEADER:
        raise ApiError(
            code="NOT_CLUB_LEADER",
            message="你不是该社团的负责人",
            status=403,
        )

    return user, membership


#统计正常社团的有效负责人数量。
def _count_effective_leaders(club):
    user_model = get_user_model()
    return ClubMembership.objects.filter(
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club_role=ClubMembership.ClubRole.LEADER,
        user__account_status=user_model.AccountStatus.ACTIVE,
    ).count()


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


# ── 请求体解析辅助 ──────────────────────────────────────────

#安全解析 JSON 请求体。
def _parse_json_body(request):
    content_type = request.content_type or ""
    if not content_type.startswith("application/json"):
        raise ApiError(
            code="INVALID_REQUEST",
            message="请求体必须使用 JSON",
            status=400,
        )
    try:
        import json as _json
        return _json.loads(request.body)
    except (_json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(
            code="INVALID_REQUEST",
            message="JSON 格式不正确",
            status=400,
        )


#解析社团 PATCH 请求体，支持 JSON 和 multipart。
#注意：Django 只对 POST 自动解析 multipart；PATCH 的 multipart 需要手动处理。
#返回 (text_fields_dict, logo_file_or_none)。
def _parse_club_patch_body(request, allowed_fields):
    content_type_full = request.content_type or ""
    content_type = content_type_full.split(";")[0].strip()

    if content_type.startswith("multipart/form-data"):
        #手动解析 multipart/form-data 请求体（Django 不会为 PATCH 自动解析）
        try:
            from django.http.multipartparser import MultiPartParser
            from io import BytesIO

            upload_handlers = request.upload_handlers
            parser = MultiPartParser(
                META=request.META,
                input_data=BytesIO(request.body),
                upload_handlers=upload_handlers,
                encoding=request.encoding or "utf-8",
            )
            post_data, files = parser.parse()
        except Exception as exc:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"请求体解析失败：{exc}",
                status=400,
            )

        text_fields = {}
        for field in allowed_fields:
            if field in post_data:
                text_fields[field] = post_data.get(field, "").strip()
        logo_file = files.get("logo")
        #拒绝不在允许列表中的字段
        for key in post_data:
            if key not in allowed_fields and key != "logo":
                raise ApiError(
                    code="INVALID_REQUEST",
                    message=f"不允许修改字段 '{key}'",
                    status=400,
                )
        return text_fields, logo_file

    if content_type == "application/json":
        body = _parse_json_body(request)
        text_fields = {}
        for field in allowed_fields:
            if field in body:
                text_fields[field] = str(body[field]).strip() if body[field] is not None else ""
        #拒绝不在允许列表中的字段
        for key in body:
            if key not in allowed_fields:
                raise ApiError(
                    code="INVALID_REQUEST",
                    message=f"不允许修改字段 '{key}'",
                    status=400,
                )
        return text_fields, None

    raise ApiError(
        code="INVALID_REQUEST",
        message="请求体必须使用 JSON 或 multipart/form-data",
        status=400,
    )


# ── PATCH /api/admin/clubs/{club_id} ──────────────────────────

#管理员修改社团允许的文本字段和 Logo。
ADMIN_UPDATE_FIELDS = {"name", "category", "introduction"}

def _admin_update_club(request, club_id):
    require_admin(request)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    if club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="已注销社团不能修改",
            status=409,
        )

    text_fields, logo_file = _parse_club_patch_body(request, ADMIN_UPDATE_FIELDS)

    if not text_fields and logo_file is None:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请至少提供一个要修改的字段",
            status=400,
        )

    #校验名称
    if "name" in text_fields:
        name = text_fields["name"]
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
        if Club.objects.filter(name=name).exclude(id=club.id).exists():
            raise ApiError(
                code="CLUB_NAME_EXISTS",
                message="社团名称已存在",
                status=409,
            )
        club.name = name

    #校验类别
    if "category" in text_fields:
        category = text_fields["category"]
        if not category:
            raise ApiError(
                code="INVALID_REQUEST",
                message="社团类别不能为空",
                status=400,
            )
        validate_category(category)
        club.category = category

    #更新简介
    if "introduction" in text_fields:
        introduction = text_fields["introduction"]
        if not introduction:
            raise ApiError(
                code="INVALID_REQUEST",
                message="社团简介不能为空",
                status=400,
            )
        club.introduction = introduction

    #更新 Logo
    if logo_file:
        club.logo = save_logo(logo_file)

    try:
        club.save()
    except IntegrityError as error:
        raise ApiError(
            code="CLUB_NAME_EXISTS",
            message="社团名称已存在",
            status=409,
        ) from error

    return success_response(
        data=serialize_club(club),
        message="社团信息修改成功",
    )


# ── POST /api/admin/clubs/{club_id}/cancel ────────────────────

def admin_cancel_club(request, club_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )
    require_admin(request)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    if club.status == Club.Status.CANCELLED:
        raise ApiError(
            code="CLUB_ALREADY_CANCELLED",
            message="社团已经注销",
            status=409,
        )

    club.status = Club.Status.CANCELLED
    club.save()

    return success_response(
        data=serialize_club(club),
        message="社团已注销",
    )


# ── PATCH /api/leader/clubs/{club_id} ─────────────────────────

#负责人修改本人负责社团的简介（Logo 通过文件上传更新）。
LEADER_UPDATE_FIELDS = {"introduction"}

def leader_club_detail(request, club_id):
    if request.method != "PATCH":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )
    require_leader_of_club(request, club_id)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    text_fields, logo_file = _parse_club_patch_body(request, LEADER_UPDATE_FIELDS)

    if not text_fields and logo_file is None:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请至少提供一个要修改的字段",
            status=400,
        )

    if "introduction" in text_fields:
        introduction = text_fields["introduction"]
        if not introduction:
            raise ApiError(
                code="INVALID_REQUEST",
                message="社团简介不能为空",
                status=400,
            )
        club.introduction = introduction

    if logo_file:
        club.logo = save_logo(logo_file)

    club.save()

    return success_response(
        data=serialize_club(club),
        message="社团信息修改成功",
    )


# ── GET /api/admin/memberships ─────────────────────────────────

#管理员查看全量成员关系记录。
@require_GET
def admin_list_memberships(request):
    require_admin(request)
    page, page_size = parse_pagination(request)

    queryset = ClubMembership.objects.select_related("user", "club").order_by("id")
    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_membership_for_admin(m) for m in items],
            page,
            page_size,
            total,
        ),
        message="成员关系列表获取成功",
    )


# ── GET /api/leader/clubs/{club_id}/members ────────────────────

#负责人（或管理员）查看社团当前在社成员。
@require_GET
def leader_list_members(request, club_id):
    #管理员也可以查看
    user_model = get_user_model()
    if request.user.is_authenticated and request.user.platform_role == user_model.PlatformRole.ADMIN:
        #验证社团存在
        try:
            Club.objects.get(id=club_id)
        except Club.DoesNotExist:
            raise ApiError(
                code="RESOURCE_NOT_FOUND",
                message="社团不存在",
                status=404,
            )
    else:
        require_leader_of_club(request, club_id)

    memberships = ClubMembership.objects.filter(
        club_id=club_id,
        member_status=ClubMembership.MemberStatus.ACTIVE,
    ).select_related("user").order_by("id")

    return success_response(
        data={
            "items": [serialize_membership_for_leader(m) for m in memberships],
        },
        message="社团成员列表获取成功",
    )


# ── POST /api/admin/clubs/{club_id}/leaders ────────────────────

#管理员从当前在社普通成员中提升负责人。
def admin_add_leader(request, club_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )
    require_admin(request)

    body = _parse_json_body(request)
    membership_id = body.get("membership_id")

    if not membership_id:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请提供 membership_id",
            status=400,
        )

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    if club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="已注销社团不能修改负责人",
            status=409,
        )

    try:
        membership = ClubMembership.objects.select_related("user").get(
            id=membership_id,
            club=club,
        )
    except ClubMembership.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="成员关系不存在",
            status=404,
        )

    if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
        raise ApiError(
            code="MEMBERSHIP_NOT_ACTIVE",
            message="该成员不在社",
            status=422,
        )

    if membership.club_role != ClubMembership.ClubRole.MEMBER:
        raise ApiError(
            code="MEMBERSHIP_NOT_ORDINARY",
            message="只能将普通成员提升为负责人",
            status=422,
        )

    user_model = get_user_model()
    if membership.user.account_status != user_model.AccountStatus.ACTIVE:
        raise ApiError(
            code="ACCOUNT_DISABLED",
            message="该学生账号已停用，不能提升为负责人",
            status=422,
        )

    membership.club_role = ClubMembership.ClubRole.LEADER
    membership.save()

    return success_response(
        data=serialize_membership_for_admin(membership),
        message="负责人添加成功",
    )


# ── DELETE /api/admin/clubs/{club_id}/leaders/{membership_id} ──

#管理员取消负责人身份，降级为普通成员。
def admin_remove_leader(request, club_id, membership_id):
    if request.method != "DELETE":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )
    require_admin(request)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    if club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="已注销社团不能修改负责人",
            status=409,
        )

    try:
        membership = ClubMembership.objects.select_related("user").get(
            id=membership_id,
            club=club,
        )
    except ClubMembership.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="成员关系不存在",
            status=404,
        )

    if membership.club_role != ClubMembership.ClubRole.LEADER:
        raise ApiError(
            code="NOT_CURRENT_LEADER",
            message="目标成员不是负责人",
            status=422,
        )

    #最后有效负责人保护
    if _count_effective_leaders(club) <= 1:
        raise ApiError(
            code="LAST_EFFECTIVE_LEADER",
            message="不能取消最后一名有效负责人",
            status=409,
        )

    membership.club_role = ClubMembership.ClubRole.MEMBER
    membership.save()

    return success_response(
        data=serialize_membership_for_admin(membership),
        message="负责人已降级为普通成员",
    )


# ── /api/admin/clubs/{club_id} 方法分发 ──────────────────────

def admin_club_detail(request, club_id):
    if request.method == "PATCH":
        return _admin_update_club(request, club_id)
    if request.method == "GET":
        #复用已有 club_detail 逻辑
        return club_detail(request, club_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )
