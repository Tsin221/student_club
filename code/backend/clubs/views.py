import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_GET, require_POST

from core.exceptions import ApiError
from core.responses import success_response

from .models import Announcement, Club, ClubMembership, JoinApplication, Notification, Post, Recruitment, Reply
from .serializers import (
    compute_recruitment_status,
    serialize_announcement,
    serialize_club,
    serialize_join_application,
    serialize_membership_for_admin,
    serialize_membership_for_leader,
    serialize_my_membership,
    serialize_notification,
    serialize_post,
    serialize_recruitment,
    serialize_reply,
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


# ═══════════════════════════════════════════════════════════════
# S06：招新发布与公开查看
# ═══════════════════════════════════════════════════════════════


# ── 辅助：查找招新所属社团的当前有效负责人 ──────────────────

#校验当前用户是招新所属社团的有效负责人。
#通过则返回 (user, membership, recruitment)。
def require_leader_of_recruitment(request, recruitment_id):
    try:
        recruitment = Recruitment.objects.select_related("club", "publisher").get(
            id=recruitment_id,
        )
    except Recruitment.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="招新信息不存在",
            status=404,
        )

    user, _membership = require_leader_of_club(request, recruitment.club_id)
    return user, _membership, recruitment


# ── GET /api/clubs/{club_id}/recruitments ─────────────────────

#学生/管理员查看社团有效招新（只返回正常社团+未结束招新）。
@require_GET
def public_list_recruitments(request, club_id):
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

    page, page_size = parse_pagination(request)

    #只返回正常社团且未结束的招新；已结束的判断依赖 ended_early 和 end_time
    from django.utils import timezone
    now = timezone.now()
    queryset = (
        Recruitment.objects
        .filter(
            club=club,
            club__status=Club.Status.ACTIVE,
            ended_early=False,
            end_time__gte=now,
        )
        .select_related("publisher")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_recruitment(r) for r in items],
            page,
            page_size,
            total,
        ),
        message="招新列表获取成功",
    )


# ── GET /api/leader/clubs/{club_id}/recruitments ──────────────
# ── POST /api/leader/clubs/{club_id}/recruitments ─────────────

#负责人招新列表（全部，含已结束）。
def _leader_list_recruitments(request, club_id):
    require_leader_of_club(request, club_id)
    page, page_size = parse_pagination(request)

    queryset = (
        Recruitment.objects
        .filter(club_id=club_id)
        .select_related("publisher")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_recruitment(r) for r in items],
            page,
            page_size,
            total,
        ),
        message="招新列表获取成功",
    )


#负责人发布招新。
def _leader_create_recruitment(request, club_id):
    user, _membership = require_leader_of_club(request, club_id)

    body = _parse_json_body(request)

    title = (body.get("title") or "").strip()
    introduction = (body.get("introduction") or "").strip()
    requirements = (body.get("requirements") or "").strip()

    #必填字段校验
    if not title:
        raise ApiError(
            code="INVALID_REQUEST",
            message="招新标题不能为空",
            status=400,
        )
    if len(title) > 200:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="招新标题不能超过 200 字",
            status=422,
        )
    if not introduction:
        raise ApiError(
            code="INVALID_REQUEST",
            message="招新简介不能为空",
            status=400,
        )
    if not requirements:
        raise ApiError(
            code="INVALID_REQUEST",
            message="招新要求不能为空",
            status=400,
        )

    #capacity 校验
    capacity = body.get("capacity")
    if capacity is None:
        raise ApiError(
            code="INVALID_REQUEST",
            message="招新人数不能为空",
            status=400,
        )
    try:
        capacity = int(capacity)
    except (TypeError, ValueError):
        raise ApiError(
            code="INVALID_CAPACITY",
            message="招新人数必须是整数",
            status=422,
        )
    if capacity <= 0:
        raise ApiError(
            code="INVALID_CAPACITY",
            message="招新人数必须大于 0",
            status=422,
        )

    #时间校验
    from django.utils import timezone
    from datetime import datetime

    start_time_str = (body.get("start_time") or "").strip()
    end_time_str = (body.get("end_time") or "").strip()

    if not start_time_str:
        raise ApiError(
            code="INVALID_REQUEST",
            message="开始时间不能为空",
            status=400,
        )
    if not end_time_str:
        raise ApiError(
            code="INVALID_REQUEST",
            message="结束时间不能为空",
            status=400,
        )

    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
    except (ValueError, TypeError):
        raise ApiError(
            code="INVALID_TIME_RANGE",
            message="时间格式不正确",
            status=422,
        )

    if start_time >= end_time:
        raise ApiError(
            code="INVALID_TIME_RANGE",
            message="开始时间必须早于结束时间",
            status=422,
        )

    recruitment = Recruitment.objects.create(
        title=title,
        introduction=introduction,
        requirements=requirements,
        capacity=capacity,
        start_time=start_time,
        end_time=end_time,
        club_id=club_id,
        publisher=user,
    )

    return success_response(
        data=serialize_recruitment(recruitment),
        message="招新发布成功",
        status=201,
    )


# /api/leader/clubs/{club_id}/recruitments 方法分发。
def leader_recruitments(request, club_id):
    if request.method == "GET":
        return _leader_list_recruitments(request, club_id)
    if request.method == "POST":
        return _leader_create_recruitment(request, club_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── PATCH /api/leader/recruitments/{recruitment_id} ────────────

#负责人修改未结束的招新。
def _leader_update_recruitment(request, recruitment_id):
    _user, _membership, recruitment = require_leader_of_recruitment(
        request, recruitment_id
    )

    #已结束的招新不能修改
    from django.utils import timezone
    now = timezone.now()
    if recruitment.ended_early or now >= recruitment.end_time:
        raise ApiError(
            code="RECRUITMENT_ENDED",
            message="已结束的招新不能修改",
            status=409,
        )

    #校验所属社团仍为正常
    if recruitment.club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="社团已注销，当前操作不可用",
            status=409,
        )

    ALLOWED_FIELDS = {"title", "introduction", "requirements", "capacity", "start_time", "end_time"}
    body = _parse_json_body(request)

    #拒绝不允许的字段
    for key in body:
        if key not in ALLOWED_FIELDS:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许修改字段 '{key}'",
                status=400,
            )

    if not body:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请至少提供一个要修改的字段",
            status=400,
        )

    #逐字段校验和更新
    if "title" in body:
        title = (body["title"] or "").strip()
        if not title:
            raise ApiError(
                code="INVALID_REQUEST",
                message="招新标题不能为空",
                status=400,
            )
        if len(title) > 200:
            raise ApiError(
                code="VALIDATION_ERROR",
                message="招新标题不能超过 200 字",
                status=422,
            )
        recruitment.title = title

    if "introduction" in body:
        introduction = (body["introduction"] or "").strip()
        if not introduction:
            raise ApiError(
                code="INVALID_REQUEST",
                message="招新简介不能为空",
                status=400,
            )
        recruitment.introduction = introduction

    if "requirements" in body:
        requirements = (body["requirements"] or "").strip()
        if not requirements:
            raise ApiError(
                code="INVALID_REQUEST",
                message="招新要求不能为空",
                status=400,
            )
        recruitment.requirements = requirements

    if "capacity" in body:
        try:
            capacity = int(body["capacity"])
        except (TypeError, ValueError):
            raise ApiError(
                code="INVALID_CAPACITY",
                message="招新人数必须是整数",
                status=422,
            )
        if capacity <= 0:
            raise ApiError(
                code="INVALID_CAPACITY",
                message="招新人数必须大于 0",
                status=422,
            )

        #校验容量不低于已通过人数
        approved_count = JoinApplication.objects.filter(
            recruitment=recruitment,
            status=JoinApplication.Status.APPROVED,
        ).count()
        if capacity < approved_count:
            raise ApiError(
                code="CAPACITY_BELOW_APPROVED",
                message=f"招新人数不能低于已通过人数（{approved_count}）",
                status=422,
            )

        recruitment.capacity = capacity

    if "start_time" in body or "end_time" in body:
        from datetime import datetime

        start_time_str = (body.get("start_time") or "").strip()
        end_time_str = (body.get("end_time") or "").strip()

        #保留未修改的字段当前值
        current_start = recruitment.start_time
        current_end = recruitment.end_time

        if start_time_str:
            try:
                current_start = datetime.fromisoformat(start_time_str)
            except (ValueError, TypeError):
                raise ApiError(
                    code="INVALID_TIME_RANGE",
                    message="时间格式不正确",
                    status=422,
                )

        if end_time_str:
            try:
                current_end = datetime.fromisoformat(end_time_str)
            except (ValueError, TypeError):
                raise ApiError(
                    code="INVALID_TIME_RANGE",
                    message="时间格式不正确",
                    status=422,
                )

        if current_start >= current_end:
            raise ApiError(
                code="INVALID_TIME_RANGE",
                message="开始时间必须早于结束时间",
                status=422,
            )

        recruitment.start_time = current_start
        recruitment.end_time = current_end

    recruitment.save()

    return success_response(
        data=serialize_recruitment(recruitment),
        message="招新修改成功",
    )


# /api/leader/recruitments/{recruitment_id} 方法分发。
def leader_recruitment_detail(request, recruitment_id):
    if request.method == "PATCH":
        return _leader_update_recruitment(request, recruitment_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── POST /api/leader/recruitments/{recruitment_id}/end ────────

#负责人提前结束招新。
def leader_end_recruitment(request, recruitment_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    _user, _membership, recruitment = require_leader_of_recruitment(
        request, recruitment_id
    )

    #已结束的不能重复结束
    if recruitment.ended_early:
        raise ApiError(
            code="RECRUITMENT_ENDED",
            message="该招新已经提前结束",
            status=409,
        )

    from django.utils import timezone
    if timezone.now() >= recruitment.end_time:
        raise ApiError(
            code="RECRUITMENT_ENDED",
            message="该招新已到期结束",
            status=409,
        )

    recruitment.ended_early = True
    recruitment.save()

    return success_response(
        data=serialize_recruitment(recruitment),
        message="招新已提前结束",
    )


# ── GET /api/admin/recruitments ────────────────────────────────

#管理员查看全量招新记录。
@require_GET
def admin_list_recruitments(request):
    require_admin(request)
    page, page_size = parse_pagination(request)

    queryset = (
        Recruitment.objects
        .select_related("club", "publisher")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_recruitment(r) for r in items],
            page,
            page_size,
            total,
        ),
        message="招新记录列表获取成功",
    )


# ═══════════════════════════════════════════════════════════════
# S07：入社申请、审核、成员创建与通知
# ═══════════════════════════════════════════════════════════════


# ── POST /api/recruitments/{recruitment_id}/applications ──────

#学生向招新提交入社申请。
def student_create_application(request, recruitment_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    user = require_active_student(request)

    #查找招新
    try:
        recruitment = Recruitment.objects.select_related("club").get(id=recruitment_id)
    except Recruitment.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="招新信息不存在",
            status=404,
        )

    club = recruitment.club

    #所属社团必须正常
    if club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="社团已注销，当前操作不可用",
            status=409,
        )

    #校验动态状态是否为"进行中"
    display_status, _approved_count = compute_recruitment_status(recruitment)
    if display_status != "进行中":
        error_map = {
            "未开始": ("RECRUITMENT_NOT_STARTED", "该招新尚未开始"),
            "已满": ("RECRUITMENT_FULL", "该招新人数已满"),
            "已结束": ("RECRUITMENT_ENDED", "该招新已结束"),
        }
        code, message = error_map.get(
            display_status,
            ("RECRUITMENT_ENDED", "该招新当前不可申请"),
        )
        raise ApiError(code=code, message=message, status=409)

    #校验申请人不在该社团
    existing_membership = ClubMembership.objects.filter(
        user=user,
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
    ).exists()
    if existing_membership:
        raise ApiError(
            code="ALREADY_CLUB_MEMBER",
            message="你已经是该社团的成员",
            status=409,
        )

    #校验无重复待审核申请
    if JoinApplication.objects.filter(
        recruitment=recruitment,
        applicant=user,
        status=JoinApplication.Status.PENDING,
    ).exists():
        raise ApiError(
            code="PENDING_APPLICATION_EXISTS",
            message="你已有一条待审核的入社申请",
            status=409,
        )

    #校验不是申请往期招新（被拒绝后只能申请该社团后续发布的新招新）
    latest_rejected = JoinApplication.objects.filter(
        applicant=user,
        club=club,
        status=JoinApplication.Status.REJECTED,
    ).order_by("-recruitment__published_at").first()
    if latest_rejected and recruitment.published_at <= latest_rejected.recruitment.published_at:
        raise ApiError(
            code="NOT_LATER_RECRUITMENT",
            message="你已被该社团拒绝，只能申请后续发布的新招新",
            status=409,
        )

    #解析请求体
    body = _parse_json_body(request)
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise ApiError(
            code="INVALID_REQUEST",
            message="申请理由不能为空",
            status=400,
        )

    application = JoinApplication.objects.create(
        applicant=user,
        applicant_name_snapshot=user.name,
        applicant_major_class_snapshot=user.major_class,
        club=club,
        recruitment=recruitment,
        reason=reason,
        status=JoinApplication.Status.PENDING,
    )

    return success_response(
        data=serialize_join_application(application),
        message="入社申请提交成功",
        status=201,
    )


# ── GET /api/me/join-applications ─────────────────────────────

#学生查看本人全部入社申请。
@require_GET
def my_join_applications(request):
    user = require_active_student(request)
    page, page_size = parse_pagination(request)

    queryset = (
        JoinApplication.objects
        .filter(applicant=user)
        .select_related("club", "recruitment")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_join_application(a) for a in items],
            page,
            page_size,
            total,
        ),
        message="入社申请列表获取成功",
    )


# ── GET /api/leader/clubs/{club_id}/join-applications ──────────

#负责人查看本社团全部入社申请。
@require_GET
def leader_join_applications(request, club_id):
    require_leader_of_club(request, club_id)
    page, page_size = parse_pagination(request)

    queryset = (
        JoinApplication.objects
        .filter(club_id=club_id)
        .select_related("applicant", "recruitment")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_join_application(a) for a in items],
            page,
            page_size,
            total,
        ),
        message="入社申请列表获取成功",
    )


# ── POST /api/leader/join-applications/{application_id}/approve ─

#负责人通过入社申请。
def leader_approve_application(request, application_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    #查申请，反查社团
    try:
        application = JoinApplication.objects.select_related(
            "club", "recruitment", "applicant",
        ).get(id=application_id)
    except JoinApplication.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="入社申请不存在",
            status=404,
        )

    #验证当前用户是该社团有效负责人
    require_leader_of_club(request, application.club_id)

    #申请必须是待审核
    if application.status != JoinApplication.Status.PENDING:
        raise ApiError(
            code="APPLICATION_NOT_PENDING",
            message="该申请已经处理",
            status=409,
        )

    #事务中执行
    try:
        with transaction.atomic():
            #重新锁定招新，检查容量
            recruitment = Recruitment.objects.select_for_update().get(
                id=application.recruitment_id,
            )
            approved_count = JoinApplication.objects.filter(
                recruitment=recruitment,
                status=JoinApplication.Status.APPROVED,
            ).count()

            if approved_count >= recruitment.capacity:
                raise ApiError(
                    code="RECRUITMENT_FULL",
                    message="招新人数已满",
                    status=409,
                )

            #重新检查申请人账号和成员状态
            user_model = get_user_model()
            applicant = application.applicant
            if applicant.account_status != user_model.AccountStatus.ACTIVE:
                raise ApiError(
                    code="APPLICANT_DISABLED",
                    message="申请人账号已停用",
                    status=422,
                )

            #检查申请人是否已在社
            active_membership = ClubMembership.objects.filter(
                user=applicant,
                club=application.club,
                member_status=ClubMembership.MemberStatus.ACTIVE,
            ).first()
            if active_membership:
                raise ApiError(
                    code="ALREADY_CLUB_MEMBER",
                    message="申请人已经是该社团成员",
                    status=409,
                )

            #更新申请状态
            application.status = JoinApplication.Status.APPROVED
            application.save()

            #创建或恢复成员关系
            membership, created = ClubMembership.objects.get_or_create(
                user=applicant,
                club=application.club,
                defaults={
                    "member_status": ClubMembership.MemberStatus.ACTIVE,
                    "club_role": ClubMembership.ClubRole.MEMBER,
                },
            )
            if not created:
                #恢复已有关系
                membership.member_status = ClubMembership.MemberStatus.ACTIVE
                membership.club_role = ClubMembership.ClubRole.MEMBER
                membership.save()

            #生成通知
            notification_content = (
                f"你在社团「{application.club.name}」的入社申请（招新：{application.recruitment.title}）"
                f"已通过审核。你现在是该社团的正式成员。"
            )
            Notification.objects.create(
                recipient=applicant,
                type=Notification.Type.APPLICATION_REVIEWED,
                content=notification_content,
            )

    except ApiError:
        raise
    except IntegrityError as error:
        raise ApiError(
            code="INVALID_REQUEST",
            message="操作失败，请稍后重试",
            status=500,
        ) from error

    return success_response(
        data={
            "application": serialize_join_application(application),
            "membership": {
                "id": membership.id,
                "user_id": applicant.id,
                "club_id": application.club_id,
                "member_status": membership.member_status,
                "club_role": membership.club_role,
            },
        },
        message="入社申请已通过",
    )


# ── POST /api/leader/join-applications/{application_id}/reject ─

#负责人拒绝入社申请。
def leader_reject_application(request, application_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    try:
        application = JoinApplication.objects.select_related(
            "club", "recruitment", "applicant",
        ).get(id=application_id)
    except JoinApplication.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="入社申请不存在",
            status=404,
        )

    #验证当前用户是该社团有效负责人
    require_leader_of_club(request, application.club_id)

    if application.status != JoinApplication.Status.PENDING:
        raise ApiError(
            code="APPLICATION_NOT_PENDING",
            message="该申请已经处理",
            status=409,
        )

    try:
        with transaction.atomic():
            application.status = JoinApplication.Status.REJECTED
            application.save()

            #生成通知
            notification_content = (
                f"你在社团「{application.club.name}」的入社申请（招新：{application.recruitment.title}）"
                f"已被拒绝。如有疑问请联系社团负责人。"
            )
            Notification.objects.create(
                recipient=application.applicant,
                type=Notification.Type.APPLICATION_REVIEWED,
                content=notification_content,
            )
    except IntegrityError as error:
        raise ApiError(
            code="INVALID_REQUEST",
            message="操作失败，请稍后重试",
            status=500,
        ) from error

    return success_response(
        data=serialize_join_application(application),
        message="入社申请已拒绝",
    )


# ── GET /api/admin/join-applications ────────────────────────────

#管理员查看全量入社申请记录（只读）。
@require_GET
def admin_join_applications(request):
    require_admin(request)
    page, page_size = parse_pagination(request)

    queryset = (
        JoinApplication.objects
        .select_related("applicant", "club", "recruitment")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_join_application(a) for a in items],
            page,
            page_size,
            total,
        ),
        message="入社申请列表获取成功",
    )


# ── GET /api/me/notifications ──────────────────────────────────

#学生查看本人通知列表。
@require_GET
def my_notifications(request):
    user = require_active_student(request)

    notifications = Notification.objects.filter(
        recipient=user,
    ).order_by("-id")

    return success_response(
        data={
            "items": [serialize_notification(n) for n in notifications],
        },
        message="通知列表获取成功",
    )


# ═══════════════════════════════════════════════════════════════
# S08：成员退出、移除和历史关系
# ═══════════════════════════════════════════════════════════════


# ── POST /api/me/memberships/{membership_id}/exit ──────────────

#学生主动退出社团。
def student_exit_membership(request, membership_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    user = require_active_student(request)

    #查找成员关系，必须属于当前用户
    try:
        membership = ClubMembership.objects.select_related("club").get(
            id=membership_id,
            user=user,
        )
    except ClubMembership.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="成员关系不存在",
            status=404,
        )

    #社团必须正常
    if membership.club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="社团已注销，当前操作不可用",
            status=409,
        )

    #必须是当前在社成员
    if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
        raise ApiError(
            code="MEMBERSHIP_INACTIVE",
            message="当前成员关系已退出或已移除",
            status=409,
        )

    #负责人不能主动退出
    if membership.club_role == ClubMembership.ClubRole.LEADER:
        raise ApiError(
            code="LEADER_CANNOT_EXIT",
            message="负责人不能直接退出社团，请先联系管理员取消负责人身份",
            status=409,
        )

    membership.member_status = ClubMembership.MemberStatus.EXITED
    membership.save()

    return success_response(
        data=serialize_my_membership(membership),
        message="已退出社团",
    )


# ── POST /api/leader/memberships/{membership_id}/remove ────────

#负责人移除普通成员。
def leader_remove_member(request, membership_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    #查找目标成员关系
    try:
        target = ClubMembership.objects.select_related("club", "user").get(
            id=membership_id,
        )
    except ClubMembership.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="成员关系不存在",
            status=404,
        )

    #验证当前用户是该社团有效负责人
    require_leader_of_club(request, target.club_id)

    #社团必须正常（require_leader_of_club 已校验，此处防御）
    if target.club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="社团已注销，当前操作不可用",
            status=409,
        )

    #目标必须是当前在社成员
    if target.member_status != ClubMembership.MemberStatus.ACTIVE:
        raise ApiError(
            code="MEMBERSHIP_INACTIVE",
            message="该成员已退出或已被移除",
            status=409,
        )

    #不能移除负责人
    if target.club_role == ClubMembership.ClubRole.LEADER:
        raise ApiError(
            code="TARGET_IS_LEADER",
            message="不能移除负责人，请先联系管理员取消负责人身份",
            status=409,
        )

    target.member_status = ClubMembership.MemberStatus.REMOVED
    target.save()

    return success_response(
        data={
            "id": target.id,
            "user_id": target.user_id,
            "club_id": target.club_id,
            "member_status": target.member_status,
            "club_role": target.club_role,
        },
        message="成员已移除",
    )


# ═══════════════════════════════════════════════════════════════
# S09：社团公告
# ═══════════════════════════════════════════════════════════════


# ── 守卫：要求用户是目标社团的当前在社成员 ──────────────

#校验当前用户是目标正常社团的当前在社成员。
#通过则返回 (user, membership)。
def require_club_member(request, club_id):
    user = require_active_student(request)

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
            code="NOT_CLUB_MEMBER",
            message="你不是该社团的成员",
            status=403,
        )

    if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
        raise ApiError(
            code="MEMBERSHIP_INACTIVE",
            message="当前成员关系已退出或已移除",
            status=403,
        )

    return user, membership


# ── GET /api/clubs/{club_id}/announcements ──────────────────

#当前在社成员分页查看正常公告（置顶优先，同组按发布时间倒序）。
@require_GET
def member_list_announcements(request, club_id):
    require_club_member(request, club_id)
    page, page_size = parse_pagination(request)

    queryset = (
        Announcement.objects
        .filter(
            club_id=club_id,
            status=Announcement.Status.NORMAL,
        )
        .select_related("publisher")
        .order_by("-is_pinned", "-published_at")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_announcement(a) for a in items],
            page,
            page_size,
            total,
        ),
        message="公告列表获取成功",
    )


# ── POST /api/leader/clubs/{club_id}/announcements ──────────

#负责人发布公告。
def _leader_create_announcement(request, club_id):
    user, _membership = require_leader_of_club(request, club_id)

    body = _parse_json_body(request)

    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    is_pinned = bool(body.get("is_pinned", False))

    #必填字段校验
    if not title:
        raise ApiError(
            code="INVALID_REQUEST",
            message="公告标题不能为空",
            status=400,
        )
    if len(title) > 200:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="公告标题不能超过 200 字",
            status=422,
        )
    if not content:
        raise ApiError(
            code="INVALID_REQUEST",
            message="公告内容不能为空",
            status=400,
        )

    announcement = Announcement.objects.create(
        title=title,
        content=content,
        club_id=club_id,
        publisher=user,
        is_pinned=is_pinned,
    )

    return success_response(
        data=serialize_announcement(announcement),
        message="公告发布成功",
        status=201,
    )


#负责人查看本社团全部公告（含已删除）。
def _leader_list_announcements(request, club_id):
    require_leader_of_club(request, club_id)
    page, page_size = parse_pagination(request)

    queryset = (
        Announcement.objects
        .filter(club_id=club_id)
        .select_related("publisher")
        .order_by("-is_pinned", "-published_at")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_announcement(a) for a in items],
            page,
            page_size,
            total,
        ),
        message="公告列表获取成功",
    )


# /api/leader/clubs/{club_id}/announcements 方法分发。
def leader_announcements(request, club_id):
    if request.method == "GET":
        return _leader_list_announcements(request, club_id)
    if request.method == "POST":
        return _leader_create_announcement(request, club_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── PATCH /api/leader/announcements/{announcement_id} ───────

#负责人修改公告（title、content、is_pinned，至少一个字段）。
def _leader_update_announcement(request, announcement_id):
    try:
        announcement = Announcement.objects.select_related("club", "publisher").get(
            id=announcement_id,
        )
    except Announcement.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="公告不存在",
            status=404,
        )

    #校验当前用户是该公告所属社团的有效负责人
    require_leader_of_club(request, announcement.club_id)

    #已删除公告不能修改
    if announcement.status == Announcement.Status.DELETED:
        raise ApiError(
            code="ANNOUNCEMENT_DELETED",
            message="已删除的公告不能修改",
            status=409,
        )

    ALLOWED_FIELDS = {"title", "content", "is_pinned"}
    body = _parse_json_body(request)

    #拒绝不允许的字段
    for key in body:
        if key not in ALLOWED_FIELDS:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许修改字段 '{key}'",
                status=400,
            )

    if not body:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请至少提供一个要修改的字段",
            status=400,
        )

    #逐字段校验和更新
    if "title" in body:
        title = (body["title"] or "").strip()
        if not title:
            raise ApiError(
                code="INVALID_REQUEST",
                message="公告标题不能为空",
                status=400,
            )
        if len(title) > 200:
            raise ApiError(
                code="VALIDATION_ERROR",
                message="公告标题不能超过 200 字",
                status=422,
            )
        announcement.title = title

    if "content" in body:
        content = (body["content"] or "").strip()
        if not content:
            raise ApiError(
                code="INVALID_REQUEST",
                message="公告内容不能为空",
                status=400,
            )
        announcement.content = content

    if "is_pinned" in body:
        announcement.is_pinned = bool(body["is_pinned"])

    announcement.save()

    return success_response(
        data=serialize_announcement(announcement),
        message="公告修改成功",
    )


# ── DELETE /api/leader/announcements/{announcement_id} ──────

#负责人逻辑删除公告。
def leader_delete_announcement(request, announcement_id):
    if request.method != "DELETE":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    try:
        announcement = Announcement.objects.select_related("club").get(
            id=announcement_id,
        )
    except Announcement.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="公告不存在",
            status=404,
        )

    #校验当前用户是该公告所属社团的有效负责人
    require_leader_of_club(request, announcement.club_id)

    #已删除公告不能重复删除
    if announcement.status == Announcement.Status.DELETED:
        raise ApiError(
            code="ANNOUNCEMENT_DELETED",
            message="该公告已经删除",
            status=409,
        )

    announcement.status = Announcement.Status.DELETED
    announcement.save()

    return success_response(
        data={
            "id": announcement.id,
            "status": announcement.status,
        },
        message="公告已删除",
    )


# /api/leader/announcements/{announcement_id} 方法分发。
def leader_announcement_detail(request, announcement_id):
    if request.method == "PATCH":
        return _leader_update_announcement(request, announcement_id)
    if request.method == "DELETE":
        return leader_delete_announcement(request, announcement_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── GET /api/admin/clubs/{club_id}/announcements ─────────────

#管理员查看已注销社团的全部公告（含已删除），正常社团返回 FORBIDDEN。
@require_GET
def admin_list_announcements(request, club_id):
    require_admin(request)

    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    #管理员只能查看已注销社团的公告历史
    if club.status != Club.Status.CANCELLED:
        raise ApiError(
            code="FORBIDDEN",
            message="只能查看已注销社团的公告历史",
            status=403,
        )

    page, page_size = parse_pagination(request)

    queryset = (
        Announcement.objects
        .filter(club_id=club_id)
        .select_related("publisher")
        .order_by("-is_pinned", "-published_at")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_announcement(a) for a in items],
            page,
            page_size,
            total,
        ),
        message="公告列表获取成功",
    )


# ═══════════════════════════════════════════════════════════════
# S10：帖子发布、列表、详情与置顶
# ═══════════════════════════════════════════════════════════════


#当前在社成员分页查看正常帖子（置顶优先，同组按自增 ID 倒序）。
def _member_list_posts(request, club_id):
    user, _membership = require_club_member(request, club_id)
    page, page_size = parse_pagination(request)

    queryset = (
        Post.objects
        .filter(
            club_id=club_id,
            status=Post.Status.NORMAL,
        )
        .select_related("author")
        .order_by("-is_pinned", "-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_post(p, current_user_id=user.id) for p in items],
            page,
            page_size,
            total,
        ),
        message="帖子列表获取成功",
    )


# ── GET /api/posts/{post_id} ──────────────────────────────

#当前在社成员查看帖子详情。
@require_GET
def post_detail(request, post_id):
    try:
        post = Post.objects.select_related("author", "club").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    #校验当前用户是目标社团的当前在社成员
    user, _membership = require_club_member(request, post.club_id)

    #已删除帖子对普通成员不可见
    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="RESOURCE_DELETED",
            message="该帖子已删除",
            status=409,
        )

    return success_response(
        data=serialize_post(post, current_user_id=user.id),
        message="帖子详情获取成功",
    )


#当前在社成员发布帖子。
def _member_create_post(request, club_id):
    user, _membership = require_club_member(request, club_id)

    body = _parse_json_body(request)

    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()

    #必填字段校验
    if not title:
        raise ApiError(
            code="INVALID_REQUEST",
            message="帖子标题不能为空",
            status=400,
        )
    if len(title) > 255:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="帖子标题不能超过 255 字",
            status=422,
        )
    if not content:
        raise ApiError(
            code="INVALID_REQUEST",
            message="帖子内容不能为空",
            status=400,
        )
    if len(content) > 5000:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="帖子内容不能超过 5000 字",
            status=422,
        )

    #拒绝不允许的字段（发布时不接受 is_pinned、status 等）
    allowed_fields = {"title", "content"}
    for key in body:
        if key not in allowed_fields:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    post = Post.objects.create(
        title=title,
        content=content,
        club_id=club_id,
        author=user,
    )

    return success_response(
        data=serialize_post(post, current_user_id=user.id),
        message="帖子发布成功",
        status=201,
    )


# /api/clubs/{club_id}/posts 方法分发。
def posts_list_or_create(request, club_id):
    if request.method == "GET":
        return _member_list_posts(request, club_id)
    if request.method == "POST":
        return _member_create_post(request, club_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── PATCH /api/leader/posts/{post_id}/pin ─────────────────

#负责人置顶或取消置顶本人负责社团的正常帖子。
def leader_pin_post(request, post_id):
    if request.method != "PATCH":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    try:
        post = Post.objects.select_related("club").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    #校验当前用户是该帖子所属社团的有效负责人
    user, _membership = require_leader_of_club(request, post.club_id)

    #已删除帖子不能置顶
    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="POST_DELETED",
            message="已删除的帖子不能置顶",
            status=409,
        )

    body = _parse_json_body(request)

    if "is_pinned" not in body:
        raise ApiError(
            code="INVALID_REQUEST",
            message="请提供 is_pinned 字段",
            status=400,
        )

    #拒绝不允许的字段
    for key in body:
        if key != "is_pinned":
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许修改字段 '{key}'",
                status=400,
            )

    post.is_pinned = bool(body["is_pinned"])
    post.save()

    return success_response(
        data=serialize_post(post, current_user_id=user.id),
        message="帖子置顶状态已更新",
    )


# ═══════════════════════════════════════════════════════════════
# S11：帖子回复与作者通知
# ═══════════════════════════════════════════════════════════════


# ── GET /api/posts/{post_id}/replies ──────────────────────

#当前在社成员查看帖子的正常回复（按自增 ID 正序，即发布先后）。
@require_GET
def list_replies(request, post_id):
    try:
        post = Post.objects.select_related("club").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    #校验当前用户是目标社团的当前在社成员
    user, _membership = require_club_member(request, post.club_id)

    #已删除帖子对普通成员不可见
    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="RESOURCE_DELETED",
            message="该帖子已删除",
            status=409,
        )

    page, page_size = parse_pagination(request)

    queryset = (
        Reply.objects
        .filter(
            post=post,
            status=Reply.Status.NORMAL,
        )
        .select_related("author")
        .order_by("id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_reply(r) for r in items],
            page,
            page_size,
            total,
        ),
        message="回复列表获取成功",
    )


# ── POST /api/posts/{post_id}/replies ─────────────────────

#当前在社成员回复帖子，帖子作者收到通知。
def create_reply(request, post_id):
    if request.method != "POST":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    try:
        post = Post.objects.select_related("club", "author").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    #校验当前用户是目标社团的当前在社成员
    user, _membership = require_club_member(request, post.club_id)

    #已删除帖子不能回复
    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="POST_DELETED",
            message="已删除的帖子不能回复",
            status=409,
        )

    body = _parse_json_body(request)

    content = (body.get("content") or "").strip()

    if not content:
        raise ApiError(
            code="INVALID_REQUEST",
            message="回复内容不能为空",
            status=400,
        )
    if len(content) > 1000:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="回复内容不能超过 1000 字",
            status=422,
        )

    #拒绝不允许的字段
    for key in body:
        if key != "content":
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    #事务中创建回复和通知
    try:
        with transaction.atomic():
            reply = Reply.objects.create(
                content=content,
                post=post,
                author=user,
            )

            #作者回复自己的帖子时不发通知
            if post.author_id != user.id:
                notification_content = (
                    f"你在社团「{post.club.name}」的帖子「{post.title}」收到了一条新回复。"
                )
                Notification.objects.create(
                    recipient=post.author,
                    type=Notification.Type.REPLY,
                    content=notification_content,
                )
    except IntegrityError as error:
        raise ApiError(
            code="INVALID_REQUEST",
            message="操作失败，请稍后重试",
            status=500,
        ) from error

    return success_response(
        data=serialize_reply(reply),
        message="回复发布成功",
        status=201,
    )


# /api/posts/{post_id}/replies 方法分发。
def replies_list_or_create(request, post_id):
    if request.method == "GET":
        return list_replies(request, post_id)
    if request.method == "POST":
        return create_reply(request, post_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )
