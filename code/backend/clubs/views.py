import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.exceptions import ApiError
from core.responses import success_response

from .models import Announcement, Club, ClubEvaluation, ClubMembership, ContentReport, Feedback, JoinApplication, Notification, Post, PostLike, Recruitment, Reply
from .serializers import (
    compute_recruitment_status,
    serialize_announcement,
    serialize_club,
    serialize_club_evaluation,
    serialize_content_report,
    serialize_feedback,
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


# ═══════════════════════════════════════════════════════════════
# S12：帖子点赞
# ═══════════════════════════════════════════════════════════════


# ── POST /api/posts/{post_id}/like ──────────────────────────

#当前在社成员点赞正常帖子。
def _member_like_post(request, post_id):
    user, _membership = _require_post_accessible(request, post_id)

    #检查是否已点赞
    if PostLike.objects.filter(user=user, post_id=post_id).exists():
        raise ApiError(
            code="DUPLICATE_LIKE",
            message="你已经点赞过该帖子",
            status=409,
        )

    PostLike.objects.create(user=user, post_id=post_id)
    post = Post.objects.select_related("author").get(id=post_id)

    return success_response(
        data=serialize_post(post, current_user_id=user.id),
        message="点赞成功",
        status=201,
    )


# ── DELETE /api/posts/{post_id}/like ────────────────────────

#当前在社成员取消点赞。
def _member_unlike_post(request, post_id):
    user, _membership = _require_post_accessible(request, post_id)

    try:
        like = PostLike.objects.get(user=user, post_id=post_id)
    except PostLike.DoesNotExist:
        raise ApiError(
            code="LIKE_NOT_FOUND",
            message="你尚未点赞该帖子",
            status=404,
        )

    like.delete()
    post = Post.objects.select_related("author").get(id=post_id)

    return success_response(
        data=serialize_post(post, current_user_id=user.id),
        message="已取消点赞",
    )


# ── 守卫：校验帖子存在、用户为成员且帖子未删除 ──────────

def _require_post_accessible(request, post_id):
    """校验帖子存在、当前用户为帖子所属社团的当前在社成员且帖子未删除。
    通过则返回 (user, membership)。"""
    try:
        post = Post.objects.select_related("club").only("club_id", "status").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="POST_DELETED",
            message="该帖子已删除，无法操作",
            status=409,
        )

    return require_club_member(request, post.club_id)


# /api/posts/{post_id}/like 方法分发。
def post_like_create_or_delete(request, post_id):
    if request.method == "POST":
        return _member_like_post(request, post_id)
    if request.method == "DELETE":
        return _member_unlike_post(request, post_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ═══════════════════════════════════════════════════════════════
# S13：社团评价
# ═══════════════════════════════════════════════════════════════


# ── POST /api/clubs/{club_id}/evaluations ────────────────────

#当前在社成员提交评价（一至五星，可选文字）。
@require_POST
def create_evaluation(request, club_id):
    user, membership = require_club_member(request, club_id)

    body = _parse_json_body(request)

    #评分校验
    rating = body.get("rating")
    if rating is None or not isinstance(rating, int):
        raise ApiError(
            code="INVALID_RATING",
            message="评分不能为空且必须为整数",
            status=400,
        )
    if rating < 1 or rating > 5:
        raise ApiError(
            code="INVALID_RATING",
            message="评分只能为一至五星",
            status=400,
        )

    comment = body.get("comment")
    if comment is not None:
        if not isinstance(comment, str):
            raise ApiError(
                code="INVALID_REQUEST",
                message="评价内容必须为字符串",
                status=400,
            )
        comment = comment.strip() or None

    #拒绝不允许的字段
    allowed = {"rating", "comment"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    #同一成员关系只能有一条评价
    if ClubEvaluation.objects.filter(membership=membership).exists():
        raise ApiError(
            code="DUPLICATE_EVALUATION",
            message="你已评价过该社团，请前往「我的评价」修改",
            status=409,
        )

    evaluation = ClubEvaluation.objects.create(
        user=user,
        club=membership.club,
        membership=membership,
        rating=rating,
        comment=comment,
    )

    return success_response(
        data=serialize_club_evaluation(evaluation),
        message="评价提交成功",
        status=201,
    )


# ── GET /api/me/evaluations ─────────────────────────────────

#学生查看本人全部评价（含历史）。
@require_GET
def my_evaluations(request):
    user = require_active_student(request)

    evaluations = (
        ClubEvaluation.objects
        .filter(user=user)
        .select_related("user", "club", "membership")
        .order_by("-id")
    )

    items = [serialize_club_evaluation(e) for e in evaluations]

    return success_response(
        data={"items": items},
        message="查询成功",
    )


# ── PATCH /api/me/evaluations/{evaluation_id} ───────────────

#评价本人修改评价（仍为在社成员时才能修改）。
def update_evaluation(request, evaluation_id):
    if request.method != "PATCH":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    user = require_active_student(request)

    #查找评价
    try:
        evaluation = ClubEvaluation.objects.select_related("club", "membership").get(id=evaluation_id)
    except ClubEvaluation.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="评价不存在",
            status=404,
        )

    #只有评价本人可以修改
    if evaluation.user_id != user.id:
        raise ApiError(
            code="NOT_EVALUATION_OWNER",
            message="你只能修改自己的评价",
            status=403,
        )

    #检查社团是否正常
    if evaluation.club.status != Club.Status.ACTIVE:
        raise ApiError(
            code="CLUB_CANCELLED",
            message="社团已注销，无法修改评价",
            status=409,
        )

    #检查是否仍为在社成员
    membership = evaluation.membership
    if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
        raise ApiError(
            code="MEMBERSHIP_INACTIVE",
            message="你已退出该社团或已被移除，无法修改评价",
            status=403,
        )

    body = _parse_json_body(request)

    if not body:
        raise ApiError(
            code="INVALID_REQUEST",
            message="至少需要修改评分或评价内容之一",
            status=400,
        )

    #评分校验
    if "rating" in body:
        rating = body["rating"]
        if not isinstance(rating, int):
            raise ApiError(
                code="INVALID_RATING",
                message="评分必须为整数",
                status=400,
            )
        if rating < 1 or rating > 5:
            raise ApiError(
                code="INVALID_RATING",
                message="评分只能为一至五星",
                status=400,
            )
        evaluation.rating = rating

    #评价内容校验
    if "comment" in body:
        comment = body["comment"]
        if not isinstance(comment, str):
            raise ApiError(
                code="INVALID_REQUEST",
                message="评价内容必须为字符串",
                status=400,
            )
        evaluation.comment = comment.strip() or None

    #拒绝不允许的字段
    allowed = {"rating", "comment"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许修改字段 '{key}'",
                status=400,
            )

    evaluation.save()

    return success_response(
        data=serialize_club_evaluation(evaluation),
        message="评价修改成功",
    )


# ── GET /api/admin/evaluations ──────────────────────────────

#管理员查看全部评价记录（只读）。
@require_GET
def admin_evaluations(request):
    require_admin(request)

    page, page_size = parse_pagination(request)

    queryset = (
        ClubEvaluation.objects
        .select_related("user", "club", "membership")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)
    serialized = [serialize_club_evaluation(e) for e in items]

    return success_response(
        data=paginated_response(serialized, page, page_size, total),
        message="查询成功",
    )


# ═══════════════════════════════════════════════════════════════
# S14：意见反馈
# ═══════════════════════════════════════════════════════════════


# ── POST /api/clubs/{club_id}/feedback ───────────────────────

#当前在社成员提交反馈。
@require_POST
def create_feedback(request, club_id):
    user, membership = require_club_member(request, club_id)

    body = _parse_json_body(request)

    #内容校验
    content = body.get("content")
    if not content or not isinstance(content, str) or content.strip() == "":
        raise ApiError(
            code="INVALID_REQUEST",
            message="反馈内容不能为空",
            status=400,
        )

    content = content.strip()

    #拒绝不允许的字段
    allowed = {"content"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    feedback = Feedback.objects.create(
        submitter=user,
        club=membership.club,
        content=content,
    )

    return success_response(
        data=serialize_feedback(feedback),
        message="反馈提交成功",
        status=201,
    )


# ── GET /api/me/feedback ────────────────────────────────────

#学生查看本人全部反馈（含历史）。
@require_GET
def my_feedbacks(request):
    user = require_active_student(request)

    feedbacks = (
        Feedback.objects
        .filter(submitter=user)
        .select_related("submitter", "club")
        .order_by("-id")
    )

    items = [serialize_feedback(f) for f in feedbacks]

    return success_response(
        data={"items": items},
        message="查询成功",
    )


# ── GET /api/leader/clubs/{club_id}/feedback ─────────────────

#负责人查看本人负责社团的全部反馈。
@require_GET
def leader_feedbacks(request, club_id):
    require_leader_of_club(request, club_id)

    page, page_size = parse_pagination(request)

    queryset = (
        Feedback.objects
        .filter(club_id=club_id)
        .select_related("submitter", "club")
        .order_by("-submitted_at")
    )

    items, total = paginate(queryset, page, page_size)
    serialized = [serialize_feedback(f) for f in items]

    return success_response(
        data=paginated_response(serialized, page, page_size, total),
        message="查询成功",
    )


# ── POST /api/leader/feedback/{feedback_id}/process ──────────

#负责人处理反馈。
@require_POST
def leader_process_feedback(request, feedback_id):
    #查找反馈
    try:
        feedback = Feedback.objects.select_related("submitter", "club").get(id=feedback_id)
    except Feedback.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="反馈不存在",
            status=404,
        )

    #校验负责人身份（对反馈所属社团）
    require_leader_of_club(request, feedback.club_id)

    #检查是否已处理
    if feedback.status != Feedback.Status.PENDING:
        raise ApiError(
            code="FEEDBACK_ALREADY_PROCESSED",
            message="该反馈已处理",
            status=409,
        )

    body = _parse_json_body(request)

    #处理说明可选
    processing_note = body.get("processing_note")
    if processing_note is not None:
        if not isinstance(processing_note, str):
            raise ApiError(
                code="INVALID_REQUEST",
                message="处理说明必须为字符串",
                status=400,
            )
        processing_note = processing_note.strip() or None

    #拒绝不允许的字段
    allowed = {"processing_note"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    feedback.status = Feedback.Status.PROCESSED
    if processing_note is not None:
        feedback.processing_note = processing_note
    feedback.save()

    return success_response(
        data=serialize_feedback(feedback),
        message="反馈处理成功",
    )


# ═══════════════════════════════════════════════════════════════
# S15：内容举报
# ═══════════════════════════════════════════════════════════════


# ── POST /api/posts/{post_id}/reports ─────────────────────────

#当前在社成员举报帖子。
@require_POST
def report_post(request, post_id):
    # 查找帖子
    try:
        post = Post.objects.select_related("author", "club").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    # 帖子必须为正常状态
    if post.status != Post.Status.NORMAL:
        raise ApiError(
            code="POST_DELETED",
            message="帖子已删除，不能举报",
            status=400,
        )

    # 校验成员权限（从帖子反推社团）
    user, _membership = require_club_member(request, post.club_id)

    body = _parse_json_body(request)

    # reason 校验
    reason = body.get("reason")
    if not reason or not isinstance(reason, str) or reason.strip() == "":
        raise ApiError(
            code="INVALID_REQUEST",
            message="举报原因不能为空",
            status=400,
        )
    reason = reason.strip()

    # 拒绝不允许的字段
    allowed = {"reason"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    report = ContentReport.objects.create(
        reporter=user,
        post=post,
        reason=reason,
    )

    return success_response(
        data=serialize_content_report(report),
        message="举报提交成功",
        status=201,
    )


# ── POST /api/replies/{reply_id}/reports ──────────────────────

#当前在社成员举报回复。
@require_POST
def report_reply(request, reply_id):
    # 查找回复
    try:
        reply = Reply.objects.select_related("author", "post", "post__club", "post__author").get(id=reply_id)
    except Reply.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="回复不存在",
            status=404,
        )

    # 回复和父帖必须为正常状态
    if reply.status != Reply.Status.NORMAL:
        raise ApiError(
            code="REPLY_DELETED",
            message="回复已删除，不能举报",
            status=400,
        )
    if reply.post.status != Post.Status.NORMAL:
        raise ApiError(
            code="POST_DELETED",
            message="帖子已删除，不能举报其回复",
            status=400,
        )

    # 校验成员权限（从父帖反推社团）
    user, _membership = require_club_member(request, reply.post.club_id)

    body = _parse_json_body(request)

    # reason 校验
    reason = body.get("reason")
    if not reason or not isinstance(reason, str) or reason.strip() == "":
        raise ApiError(
            code="INVALID_REQUEST",
            message="举报原因不能为空",
            status=400,
        )
    reason = reason.strip()

    # 拒绝不允许的字段
    allowed = {"reason"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    report = ContentReport.objects.create(
        reporter=user,
        reply=reply,
        reason=reason,
    )

    return success_response(
        data=serialize_content_report(report),
        message="举报提交成功",
        status=201,
    )


# ── GET /api/leader/clubs/{club_id}/reports ───────────────────

#负责人查看本人负责社团的举报列表。
@require_GET
def leader_reports(request, club_id):
    require_leader_of_club(request, club_id)

    page, page_size = parse_pagination(request)

    # 过滤该社团的举报：post__club_id=club_id 或 reply__post__club_id=club_id
    from django.db.models import Q

    queryset = (
        ContentReport.objects
        .filter(
            Q(post__club_id=club_id) | Q(reply__post__club_id=club_id)
        )
        .select_related("reporter", "post", "post__author", "reply", "reply__author", "reply__post")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)
    serialized = [serialize_content_report(r, include_target=True) for r in items]

    return success_response(
        data=paginated_response(serialized, page, page_size, total),
        message="查询成功",
    )


# ── POST /api/leader/reports/{report_id}/process ──────────────

#负责人处理举报。
@require_POST
def leader_process_report(request, report_id):
    # 查找举报
    try:
        report = ContentReport.objects.select_related(
            "reporter", "post", "post__author", "reply", "reply__author", "reply__post"
        ).get(id=report_id)
    except ContentReport.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="举报不存在",
            status=404,
        )

    # 确定举报所属社团
    if report.post_id:
        club_id = report.post.club_id
    elif report.reply_id:
        club_id = report.reply.post.club_id
    else:
        raise ApiError(
            code="INTERNAL_ERROR",
            message="举报数据异常",
            status=500,
        )

    # 校验负责人身份
    require_leader_of_club(request, club_id)

    # 检查是否已处理
    if report.status != ContentReport.Status.PENDING:
        raise ApiError(
            code="REPORT_ALREADY_PROCESSED",
            message="该举报已处理",
            status=409,
        )

    body = _parse_json_body(request)

    # status 校验
    new_status = body.get("status")
    if new_status not in (ContentReport.Status.ACCEPTED, ContentReport.Status.NOT_ACCEPTED):
        raise ApiError(
            code="INVALID_REPORT_STATUS",
            message="处理结论只能为'已采纳'或'未采纳'",
            status=400,
        )

    # processing_note 必填校验
    processing_note = body.get("processing_note")
    if not processing_note or not isinstance(processing_note, str) or processing_note.strip() == "":
        raise ApiError(
            code="PROCESSING_NOTE_REQUIRED",
            message="处理说明不能为空",
            status=400,
        )
    processing_note = processing_note.strip()

    # delete_target 校验
    delete_target = body.get("delete_target", False)
    if not isinstance(delete_target, bool):
        raise ApiError(
            code="INVALID_REQUEST",
            message="delete_target 必须为布尔值",
            status=400,
        )

    if new_status == ContentReport.Status.NOT_ACCEPTED and delete_target:
        raise ApiError(
            code="INVALID_DELETE_DECISION",
            message="未采纳举报时不能请求删除目标内容",
            status=400,
        )

    # 拒绝不允许的字段
    allowed = {"status", "processing_note", "delete_target"}
    for key in body:
        if key not in allowed:
            raise ApiError(
                code="INVALID_REQUEST",
                message=f"不允许提交字段 '{key}'",
                status=400,
            )

    # 事务内完成：更新举报状态、可选删除目标、生成通知
    with transaction.atomic():
        report.status = new_status
        report.processing_note = processing_note
        report.save()

        # 可选删除目标内容
        target_deleted = False
        if new_status == ContentReport.Status.ACCEPTED and delete_target:
            if report.post_id and report.post.status == Post.Status.NORMAL:
                report.post.status = Post.Status.DELETED
                report.post.save()
                target_deleted = True
            elif report.reply_id and report.reply.status == Reply.Status.NORMAL:
                report.reply.status = Reply.Status.DELETED
                report.reply.save()
                target_deleted = True
            # 目标已删除时不重复操作

        # 生成通知
        Notification.objects.create(
            recipient=report.reporter,
            type=Notification.Type.REPORT_PROCESSED,
            content=f"您的举报已处理：{new_status}",
        )

    response_data = serialize_content_report(report, include_target=True)
    if target_deleted:
        if report.post_id:
            response_data["target"]["status"] = "已删除"
        elif report.reply_id:
            response_data["target"]["status"] = "已删除"

    return success_response(
        data=response_data,
        message="举报处理成功",
    )


# ═══════════════════════════════════════════════════════════════
# S16：内容逻辑删除和管理员内容管理
# ═══════════════════════════════════════════════════════════════


# ── DELETE /api/posts/{post_id} ────────────────────────────

#作者、负责人或管理员逻辑删除帖子。
def _delete_post(request, post_id):
    if request.method != "DELETE":
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

    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="POST_DELETED",
            message="该帖子已删除",
            status=409,
        )

    # 按优先级尝试授权：作者（仍有内部权限）→ 负责人 → 管理员
    user = request.user

    # 1）管理员可删除全部帖子
    if user.is_authenticated:
        user_model = get_user_model()
        if user.platform_role == user_model.PlatformRole.ADMIN:
            post.status = Post.Status.DELETED
            post.save()
            return success_response(
                data={"id": post.id, "status": post.status},
                message="帖子已删除",
            )

    # 2）作者删除 —— 必须在目标社团仍有内部权限
    if user.is_authenticated and user.id == post.author_id:
        try:
            membership = ClubMembership.objects.get(user=user, club_id=post.club_id)
        except ClubMembership.DoesNotExist:
            raise ApiError(
                code="MEMBERSHIP_INACTIVE",
                message="你已不是该社团的成员，无法删除帖子",
                status=403,
            )
        if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
            raise ApiError(
                code="MEMBERSHIP_INACTIVE",
                message="你已不是该社团的成员，无法删除帖子",
                status=403,
            )
        # 社团也必须正常
        if membership.club.status != Club.Status.ACTIVE:
            raise ApiError(
                code="CLUB_CANCELLED",
                message="社团已注销，当前操作不可用",
                status=409,
            )
        post.status = Post.Status.DELETED
        post.save()
        return success_response(
            data={"id": post.id, "status": post.status},
            message="帖子已删除",
        )

    # 3）负责人删除（只对确实是某社团负责人的用户透传 NOT_CLUB_LEADER）
    if user.is_authenticated:
        try:
            require_leader_of_club(request, post.club_id)
        except ApiError as e:
            # 如果用户是其他社团的负责人，透传 NOT_CLUB_LEADER
            if e.code == "NOT_CLUB_LEADER" and ClubMembership.objects.filter(
                user=user,
                club_role=ClubMembership.ClubRole.LEADER,
                member_status=ClubMembership.MemberStatus.ACTIVE,
            ).exists():
                raise
        else:
            post.status = Post.Status.DELETED
            post.save()
            return success_response(
                data={"id": post.id, "status": post.status},
                message="帖子已删除",
            )

    # 4）未认证 → 401
    if not user.is_authenticated:
        raise ApiError(
            code="UNAUTHENTICATED",
            message="请先登录",
            status=401,
        )

    # 5）都不满足 → 403
    raise ApiError(
        code="FORBIDDEN",
        message="你没有权限删除该帖子",
        status=403,
    )


# ── DELETE /api/replies/{reply_id} ──────────────────────────

#作者、负责人或管理员逻辑删除回复。
def _delete_reply(request, reply_id):
    if request.method != "DELETE":
        raise ApiError(
            code="INVALID_REQUEST",
            message="不支持的请求方法",
            status=405,
        )

    try:
        reply = Reply.objects.select_related("post", "author").get(id=reply_id)
    except Reply.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="回复不存在",
            status=404,
        )

    if reply.status == Reply.Status.DELETED:
        raise ApiError(
            code="REPLY_DELETED",
            message="该回复已删除",
            status=409,
        )

    user = request.user

    # 1）管理员可删除全部回复
    if user.is_authenticated:
        user_model = get_user_model()
        if user.platform_role == user_model.PlatformRole.ADMIN:
            reply.status = Reply.Status.DELETED
            reply.save()
            return success_response(
                data={"id": reply.id, "status": reply.status},
                message="回复已删除",
            )

    # 2）作者删除 —— 父帖不能已删除，且必须在目标社团仍有内部权限
    if user.is_authenticated and user.id == reply.author_id:
        if reply.post.status == Post.Status.DELETED:
            raise ApiError(
                code="POST_DELETED",
                message="该回复所属的帖子已删除",
                status=409,
            )
        try:
            membership = ClubMembership.objects.get(
                user=user, club_id=reply.post.club_id,
            )
        except ClubMembership.DoesNotExist:
            raise ApiError(
                code="MEMBERSHIP_INACTIVE",
                message="你已不是该社团的成员，无法删除回复",
                status=403,
            )
        if membership.member_status != ClubMembership.MemberStatus.ACTIVE:
            raise ApiError(
                code="MEMBERSHIP_INACTIVE",
                message="你已不是该社团的成员，无法删除回复",
                status=403,
            )
        if membership.club.status != Club.Status.ACTIVE:
            raise ApiError(
                code="CLUB_CANCELLED",
                message="社团已注销，当前操作不可用",
                status=409,
            )
        reply.status = Reply.Status.DELETED
        reply.save()
        return success_response(
            data={"id": reply.id, "status": reply.status},
            message="回复已删除",
        )

    # 3）负责人删除（只对确实是某社团负责人的用户透传 NOT_CLUB_LEADER）
    if user.is_authenticated:
        try:
            require_leader_of_club(request, reply.post.club_id)
        except ApiError as e:
            if e.code == "NOT_CLUB_LEADER" and ClubMembership.objects.filter(
                user=user,
                club_role=ClubMembership.ClubRole.LEADER,
                member_status=ClubMembership.MemberStatus.ACTIVE,
            ).exists():
                raise
        else:
            reply.status = Reply.Status.DELETED
            reply.save()
            return success_response(
                data={"id": reply.id, "status": reply.status},
                message="回复已删除",
            )

    # 4）未认证 → 401
    if not user.is_authenticated:
        raise ApiError(
            code="UNAUTHENTICATED",
            message="请先登录",
            status=401,
        )

    # 5）都不满足 → 403
    raise ApiError(
        code="FORBIDDEN",
        message="你没有权限删除该回复",
        status=403,
    )


# /api/posts/{post_id} 方法分发（GET + DELETE）。
def post_detail_or_delete(request, post_id):
    if request.method == "GET":
        return post_detail(request, post_id)
    if request.method == "DELETE":
        return _delete_post(request, post_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# /api/replies/{reply_id}（DELETE）。
def reply_delete(request, reply_id):
    if request.method == "DELETE":
        return _delete_reply(request, reply_id)
    raise ApiError(
        code="INVALID_REQUEST",
        message="不支持的请求方法",
        status=405,
    )


# ── GET /api/admin/posts ───────────────────────────────────

#管理员查看全部帖子（含已删除）。
@require_GET
def admin_list_posts(request):
    require_admin(request)
    page, page_size = parse_pagination(request)

    queryset = (
        Post.objects
        .select_related("author", "club")
        .order_by("-id")
    )

    items, total = paginate(queryset, page, page_size)

    return success_response(
        data=paginated_response(
            [serialize_post(p, current_user_id=request.user.id) for p in items],
            page,
            page_size,
            total,
        ),
        message="帖子列表获取成功",
    )


# ── GET /api/admin/replies ─────────────────────────────────

#管理员查看全部回复（含已删除）。
@require_GET
def admin_list_replies(request):
    require_admin(request)
    page, page_size = parse_pagination(request)

    queryset = (
        Reply.objects
        .select_related("author", "post")
        .order_by("-id")
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


# ── S17：帖子 AI ──────────────────────────────────────────────

#AI 操作白名单
_VALID_AI_OPERATIONS = {"总结", "提取主要观点", "问答"}

#DeepSeek 系统提示
_AI_SYSTEM_PROMPT = (
    "你是一个社团帖子助手。请严格基于用户提供的帖子内容、标题和回复来回答问题。"
    "如果问题无法根据当前帖子内容确定答案，请直接回复「根据当前帖子内容无法确定」。"
    "不要编造信息，不要使用外部知识。回复使用中文。"
)


def _call_deepseek(system_prompt: str, user_prompt: str) -> str:
    """调用 DeepSeek API 并返回回答文本。"""
    from django.conf import settings
    import json as _json
    from urllib import request, error as urllib_error

    api_url = settings.DEEPSEEK_API_URL
    api_key = settings.DEEPSEEK_API_KEY
    model = settings.DEEPSEEK_MODEL

    if not api_key:
        raise ApiError(
            code="DEEPSEEK_CALL_FAILED",
            message="DeepSeek API 密钥未配置",
            status=502,
        )

    payload = _json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        raise ApiError(
            code="DEEPSEEK_CALL_FAILED",
            message=f"DeepSeek API 调用失败（HTTP {exc.code}）",
            status=502,
        )
    except urllib_error.URLError:
        raise ApiError(
            code="DEEPSEEK_CALL_FAILED",
            message="无法连接到 DeepSeek API，请检查网络或 API 地址",
            status=502,
        )
    except Exception:
        raise ApiError(
            code="DEEPSEEK_CALL_FAILED",
            message="DeepSeek API 调用失败，请稍后重试",
            status=502,
        )

    #提取回答文本
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ApiError(
            code="DEEPSEEK_CALL_FAILED",
            message="DeepSeek API 返回格式异常",
            status=502,
        )


def _build_ai_user_prompt(post, replies, operation, question):
    """构建发送给 DeepSeek 的用户提示词。"""
    lines = [f"【帖子标题】{post.title}", f"【帖子正文】{post.content}"]

    if replies:
        lines.append("")
        lines.append("【回复列表】")
        for i, reply in enumerate(replies, 1):
            author_name = reply.author.username
            lines.append(f"{i}. {author_name}：{reply.content}")

    full_content = "\n".join(lines)

    #内容截断
    from django.conf import settings
    max_chars = settings.AI_MAX_CONTENT_CHARS
    truncated = False

    if len(full_content) > max_chars:
        full_content = full_content[:max_chars]
        truncated = True
        truncation_warning = "（注意：内容较长，后续回复已被截断，本次回答可能未包含全部回复）"
    else:
        truncation_warning = ""

    if operation == "总结":
        task = "请对以上帖子和回复进行总结。"
    elif operation == "提取主要观点":
        task = "请提取以上帖子和回复中的主要观点。"
    else:
        task = f"请基于以上帖子和回复内容回答以下问题：{question}"

    user_prompt = f"{full_content}\n\n{truncation_warning}\n\n{task}"
    return user_prompt, truncated


@require_POST
def post_ai(request, post_id):
    """POST /api/posts/{post_id}/ai —— 对帖子进行 AI 总结/观点提取/问答。"""
    body = _parse_json_body(request)

    #校验操作类型
    operation = (body.get("operation") or "").strip()
    if operation not in _VALID_AI_OPERATIONS:
        raise ApiError(
            code="INVALID_AI_OPERATION",
            message=f"AI 操作必须是以下之一：{'、'.join(sorted(_VALID_AI_OPERATIONS))}",
            status=422,
        )

    #问答操作必须提供问题
    question = (body.get("question") or "").strip()
    if operation == "问答" and not question:
        raise ApiError(
            code="QUESTION_REQUIRED",
            message="问答操作必须提供问题",
            status=422,
        )

    #禁止其他操作携带无关输入
    if operation != "问答" and question:
        raise ApiError(
            code="VALIDATION_ERROR",
            message=f"「{operation}」操作不接受额外输入",
            status=422,
        )

    #获取帖子并校验状态
    try:
        post = Post.objects.select_related("author", "club").get(id=post_id)
    except Post.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="帖子不存在",
            status=404,
        )

    if post.status == Post.Status.DELETED:
        raise ApiError(
            code="POST_DELETED",
            message="该帖子已删除，无法使用 AI",
            status=409,
        )

    #校验成员权限
    user, _membership = require_club_member(request, post.club_id)

    #收集当前用户有权查看的正常回复
    replies = list(
        Reply.objects
        .filter(post=post, status=Reply.Status.NORMAL)
        .select_related("author")
        .order_by("id")
    )

    #构建提示词并调用 DeepSeek
    user_prompt, truncated = _build_ai_user_prompt(post, replies, operation, question)
    answer = _call_deepseek(_AI_SYSTEM_PROMPT, user_prompt)

    data = {"answer": answer, "truncated": truncated}
    if truncated:
        data["warning"] = "内容较长，本次回答可能未包含全部回复"

    return success_response(data=data, message="AI 回答生成成功")


# ── S18：AI 文档生成 ────────────────────────────────────────────

#AI 文档类型白名单
_VALID_AI_DOC_TYPES = {"社团公告", "招新文案", "社团介绍"}

#AI 文档生成系统提示
_AI_DOC_SYSTEM_PROMPT = (
    "你是一个高校社团文档撰写助手。请严格基于用户提供的社团信息和要求来撰写文档。"
    "如果用户提供的信息不足以完成文档，请在草稿中用「[此处需要补充]」标记，不要编造具体信息。"
    "生成的内容应该是可直接使用的纯文本草稿，语言正式、条理清晰。"
    "回复使用中文，只返回文档正文，不要添加额外的解释或说明。"
)


def _build_document_user_prompt(club, document_type, body):
    """构建 AI 文档生成的用户提示词。"""
    from django.conf import settings

    lines = []
    lines.append(f"请为以下社团撰写一份{document_type}草稿。")
    lines.append("")
    lines.append("【社团基本信息】")
    lines.append(f"社团名称：{club.name}")
    lines.append(f"社团类别：{club.category}")
    if club.introduction:
        lines.append(f"社团简介：{club.introduction}")
    lines.append("")

    #收集用户输入的可选字段
    has_user_input = False
    field_labels = {
        "title_or_topic": "标题/主题",
        "main_content": "主要内容",
        "audience": "面向对象",
        "time": "时间",
        "location": "地点",
        "contact": "联系方式",
        "expected_length": "期望字数",
        "style": "文风",
        "additional_requirements": "其他补充要求",
    }

    for field, label in field_labels.items():
        value = (body.get(field) or "").strip()
        if value:
            if not has_user_input:
                lines.append("【用户要求】")
                has_user_input = True
            lines.append(f"{label}：{value}")

    prompt = "\n".join(lines)

    #如果内容超长则截断
    max_chars = settings.AI_MAX_CONTENT_CHARS
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars]

    return prompt


@require_POST
def leader_ai_documents(request, club_id):
    """POST /api/leader/clubs/{club_id}/ai-documents —— 为社团生成 AI 文档草稿。"""
    body = _parse_json_body(request)

    #校验 document_type
    document_type = (body.get("document_type") or "").strip()
    if not document_type:
        raise ApiError(
            code="INVALID_DOCUMENT_TYPE",
            message="请选择文档类型",
            status=422,
        )
    if document_type not in _VALID_AI_DOC_TYPES:
        raise ApiError(
            code="INVALID_DOCUMENT_TYPE",
            message=f"文档类型必须是以下之一：{'、'.join(sorted(_VALID_AI_DOC_TYPES))}",
            status=422,
        )

    #校验负责人权限（该函数内部已确保俱乐部存在且状态正常）
    user, _membership = require_leader_of_club(request, club_id)

    #获取社团完整信息用于构建提示词
    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise ApiError(
            code="RESOURCE_NOT_FOUND",
            message="社团不存在",
            status=404,
        )

    #构建提示词并调用 DeepSeek
    user_prompt = _build_document_user_prompt(club, document_type, body)
    draft = _call_deepseek(_AI_DOC_SYSTEM_PROMPT, user_prompt)

    return success_response(data={"draft": draft}, message="AI 文档草稿生成成功")


# ── S19：三类数据概览 ────────────────────────────────────────


@require_GET
def admin_overview(request):
    """GET /api/admin/overview —— 管理员查看全局数据概览。"""
    require_admin(request)

    User = get_user_model()
    user_count = User.objects.filter(platform_role=User.PlatformRole.STUDENT).count()
    normal_club_count = Club.objects.filter(status=Club.Status.ACTIVE).count()

    return success_response(
        data={
            "user_count": user_count,
            "normal_club_count": normal_club_count,
        },
    )


@require_GET
def leader_overview(request, club_id):
    """GET /api/leader/clubs/{club_id}/overview —— 负责人查看当前社团数据概览。"""
    _user, _membership = require_leader_of_club(request, club_id)

    #在社成员数
    active_member_count = ClubMembership.objects.filter(
        club_id=club_id,
        member_status=ClubMembership.MemberStatus.ACTIVE,
    ).count()

    #待审核申请数
    pending_application_count = JoinApplication.objects.filter(
        club_id=club_id,
        status=JoinApplication.Status.PENDING,
    ).count()

    #当前招新数（动态展示状态不是“已结束”的招新）
    current_recruitment_count = Recruitment.objects.filter(
        club_id=club_id,
        ended_early=False,
        end_time__gt=timezone.now(),
    ).count()

    #正常帖子数
    post_count = Post.objects.filter(
        club_id=club_id,
        status=Post.Status.NORMAL,
    ).count()

    #待处理反馈数
    pending_feedback_count = Feedback.objects.filter(
        club_id=club_id,
        status=Feedback.Status.PENDING,
    ).count()

    #待处理举报数（通过 post 或 reply 关联到当前社团）
    pending_report_count = ContentReport.objects.filter(
        status=ContentReport.Status.PENDING,
    ).filter(
        Q(post__club_id=club_id) | Q(reply__post__club_id=club_id),
    ).count()

    return success_response(
        data={
            "active_member_count": active_member_count,
            "pending_application_count": pending_application_count,
            "current_recruitment_count": current_recruitment_count,
            "post_count": post_count,
            "pending_feedback_count": pending_feedback_count,
            "pending_report_count": pending_report_count,
        },
    )


@require_GET
def my_overview(request):
    """GET /api/me/overview —— 学生查看本人数据概览。"""
    require_active_student(request)

    #当前加入正常社团数（在社 + 社团正常）
    joined_normal_club_count = ClubMembership.objects.filter(
        user=request.user,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club__status=Club.Status.ACTIVE,
    ).count()

    #本人全部入社申请（按申请时间倒序）
    applications = JoinApplication.objects.filter(
        applicant=request.user,
    ).select_related("club", "recruitment").order_by("-applied_at")

    return success_response(
        data={
            "joined_normal_club_count": joined_normal_club_count,
            "join_applications": [
                serialize_join_application(a) for a in applications
            ],
        },
    )
