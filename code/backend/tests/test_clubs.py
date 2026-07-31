import io
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

LOGIN_URL = "/api/auth/login"


def response_body(response):
    return json.loads(response.content)


def create_student(**overrides):
    """创建学生用户。"""
    data = {
        "username": "test_student",
        "password": "StrongPass!2026",
        "name": "测试学生",
        "phone": "13800001111",
        "major_class": "计算机1班",
        "grade": "2026",
        **overrides,
    }
    return get_user_model().objects.create_user(**data)


def create_admin(username="admin_test", password="AdminPass!2026"):
    """创建系统管理员。"""
    return get_user_model().objects.create_user(
        username=username,
        password=password,
        name="系统管理员",
        phone="",
        major_class="",
        grade="",
        platform_role=get_user_model().PlatformRole.ADMIN,
        account_status=get_user_model().AccountStatus.ACTIVE,
    )


def login(client, username, password):
    """执行登录并返回响应。"""
    return client.post(
        LOGIN_URL,
        data=json.dumps({
            "username": username,
            "password": password,
        }),
        content_type="application/json",
    )


def login_as_admin():
    """创建管理员并登录，返回已认证客户端和管理员用户。"""
    admin = create_admin()
    client = Client()
    resp = login(client, admin.username, "AdminPass!2026")
    assert resp.status_code == 200
    return client, admin


def login_as_student():
    """创建学生并登录，返回已认证客户端和学生用户。"""
    student = create_student()
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    assert resp.status_code == 200
    return client, student


#生成一个简单的 PNG 文件（1x1 像素），用于 Logo 上传测试。
def make_logo_file():
    #最小的有效 PNG（1x1 白色像素）
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return io.BytesIO(png_bytes)


#创建社团的 multipart 数据构建辅助函数。
def build_create_club_data(name, category, introduction, logo_file, leader_ids):
    """构建创建社团的 multipart form data，返回 (content_type, body)。"""
    from django.test.client import BOUNDARY, encode_multipart

    data = {
        "name": name,
        "category": category,
        "introduction": introduction,
        "leader_user_ids": json.dumps(leader_ids),
    }
    if logo_file is not None:
        data["logo"] = logo_file

    body = encode_multipart(BOUNDARY, data)
    content_type = f"multipart/form-data; boundary={BOUNDARY}"
    return content_type, body


#辅助函数：发送创建社团的 POST 请求。
def post_create_club(client, name, category, introduction, logo_file, leader_ids):
    """向 /api/admin/clubs 发送创建请求。"""
    content_type, body = build_create_club_data(
        name, category, introduction, logo_file, leader_ids,
    )
    return client.post(
        "/api/admin/clubs",
        data=body,
        content_type=content_type,
    )


# ── POST /api/admin/clubs ────────────────────────────────────


@pytest.mark.django_db
def test_admin_can_create_club_with_leaders():
    """管理员可以创建社团并指定初始负责人。"""
    leader1 = create_student(username="leader1", name="负责人一")
    leader2 = create_student(username="leader2", name="负责人二")
    client, admin = login_as_admin()

    logo = make_logo_file()
    logo.name = "test_logo.png"

    response = post_create_club(
        client,
        name="测试社团",
        category="学术科技",
        introduction="这是一个测试社团。",
        logo_file=logo,
        leader_ids=[leader1.id, leader2.id],
    )

    assert response.status_code == 201
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["club"]["name"] == "测试社团"
    assert body["data"]["club"]["category"] == "学术科技"
    assert body["data"]["club"]["status"] == "normal"
    assert body["data"]["club"]["logo"].startswith("logos/")

    leaders_data = body["data"]["leaders"]
    assert len(leaders_data) == 2
    leader_user_ids = [l["user"]["id"] for l in leaders_data]
    assert leader1.id in leader_user_ids
    assert leader2.id in leader_user_ids
    for ld in leaders_data:
        assert ld["club_role"] == "leader"
        assert ld["member_status"] == "active"


@pytest.mark.django_db
def test_create_club_transaction_atomic_with_invalid_leader():
    """初始负责人无效时，社团也不创建。"""
    leader = create_student(username="leader1")
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="原子性测试社团",
        category="体育竞技",
        introduction="测试事务原子性。",
        logo_file=logo,
        leader_ids=[leader.id, 99999],
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "INITIAL_LEADER_INVALID"

    #社团不应存在
    from clubs.models import Club
    assert not Club.objects.filter(name="原子性测试社团").exists()


@pytest.mark.django_db
def test_create_club_rejects_duplicate_name():
    """社团名称重复时返回 CLUB_NAME_EXISTS。"""
    leader = create_student(username="leader1")
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"

    resp1 = post_create_club(
        client,
        name="唯一社团名",
        category="文化艺术",
        introduction="第一。",
        logo_file=logo,
        leader_ids=[leader.id],
    )
    assert resp1.status_code == 201

    logo2 = make_logo_file()
    logo2.name = "logo2.png"

    resp2 = post_create_club(
        client,
        name="唯一社团名",
        category="公益实践",
        introduction="第二。",
        logo_file=logo2,
        leader_ids=[leader.id],
    )
    assert resp2.status_code == 409
    assert response_body(resp2)["code"] == "CLUB_NAME_EXISTS"


@pytest.mark.django_db
def test_create_club_rejects_invalid_category():
    """类别不在枚举中返回 INVALID_CLUB_CATEGORY。"""
    leader = create_student()
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="类别测试",
        category="不存在的类别",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[leader.id],
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "INVALID_CLUB_CATEGORY"


@pytest.mark.django_db
def test_create_club_rejects_missing_logo():
    """缺少 Logo 返回 LOGO_REQUIRED。"""
    leader = create_student()
    client, _ = login_as_admin()

    response = post_create_club(
        client,
        name="无Logo社团",
        category="兴趣爱好",
        introduction="没有 Logo。",
        logo_file=None,
        leader_ids=[leader.id],
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "LOGO_REQUIRED"


@pytest.mark.django_db
def test_create_club_rejects_empty_leaders():
    """初始负责人列表为空返回 INITIAL_LEADER_REQUIRED。"""
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="无负责人社团",
        category="兴趣爱好",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[],
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INITIAL_LEADER_REQUIRED"


@pytest.mark.django_db
def test_create_club_rejects_disabled_leader():
    """初始负责人为已停用学生返回 INITIAL_LEADER_INVALID。"""
    disabled_student = create_student(
        username="disabled_student",
        account_status=get_user_model().AccountStatus.DISABLED,
    )
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="停用负责人社团",
        category="其他",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[disabled_student.id],
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "INITIAL_LEADER_INVALID"


@pytest.mark.django_db
def test_create_club_rejects_admin_as_leader():
    """管理员不能作为初始负责人。"""
    admin2 = create_admin(username="admin2", password="Admin2Pass!2026")
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="管理员负责人社团",
        category="其他",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[admin2.id],
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "INITIAL_LEADER_INVALID"


@pytest.mark.django_db
def test_create_club_rejects_duplicate_leader_ids():
    """重复的负责人 ID 返回错误。"""
    leader = create_student()
    client, _ = login_as_admin()

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="重复负责人社团",
        category="其他",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[leader.id, leader.id],
    )

    assert response.status_code == 400
    assert "重复" in response_body(response)["message"]


# ── 创建社团权限 ──────────────────────────────────────────────


@pytest.mark.django_db
def test_create_club_rejects_unauthenticated():
    """未登录不能创建社团。"""
    logo = make_logo_file()
    logo.name = "logo.png"

    response = post_create_club(
        Client(),
        name="未登录社团",
        category="其他",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[1],
    )

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_create_club_rejects_student():
    """学生不能创建社团。"""
    leader = create_student(username="leader1")
    student = create_student(username="ordinary_student")
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    assert resp.status_code == 200

    logo = make_logo_file()
    logo.name = "logo.png"
    response = post_create_club(
        client,
        name="学生创建社团",
        category="其他",
        introduction="测试。",
        logo_file=logo,
        leader_ids=[leader.id],
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


# ── GET /api/admin/clubs ──────────────────────────────────────


@pytest.mark.django_db
def test_admin_list_clubs_includes_all():
    """管理员列表包含正常和已注销社团。"""
    from clubs.models import Club

    Club.objects.create(
        name="正常社团",
        category="学术科技",
        introduction="简介",
        logo="logos/test1.png",
        status=Club.Status.ACTIVE,
    )
    Club.objects.create(
        name="已注销社团",
        category="文化艺术",
        introduction="简介",
        logo="logos/test2.png",
        status=Club.Status.CANCELLED,
    )
    client, _ = login_as_admin()

    response = client.get("/api/admin/clubs")

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    names = [c["name"] for c in body["data"]["items"]]
    assert "正常社团" in names
    assert "已注销社团" in names


@pytest.mark.django_db
def test_admin_list_clubs_pagination():
    """管理员列表分页正确。"""
    from clubs.models import Club

    for i in range(5):
        Club.objects.create(
            name=f"分页社团{i}",
            category="其他",
            introduction=f"简介{i}",
            logo=f"logos/p{i}.png",
        )
    client, _ = login_as_admin()

    response = client.get("/api/admin/clubs?page=1&page_size=2")

    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert len(body["data"]["items"]) <= 2
    assert body["data"]["total"] >= 5


@pytest.mark.django_db
def test_admin_list_clubs_rejects_student():
    """学生不能访问管理员社团列表。"""
    client, student = login_as_student()

    response = client.get("/api/admin/clubs")

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


# ── GET /api/clubs ───────────────────────────────────────────


@pytest.mark.django_db
def test_public_list_only_returns_normal_clubs():
    """公开列表只返回正常社团。"""
    from clubs.models import Club

    Club.objects.create(
        name="公开社团",
        category="学术科技",
        introduction="简介",
        logo="logos/pub.png",
        status=Club.Status.ACTIVE,
    )
    Club.objects.create(
        name="隐藏社团",
        category="文化艺术",
        introduction="简介",
        logo="logos/hid.png",
        status=Club.Status.CANCELLED,
    )
    client, _ = login_as_student()

    response = client.get("/api/clubs")

    assert response.status_code == 200
    body = response_body(response)
    names = [c["name"] for c in body["data"]["items"]]
    assert "公开社团" in names
    assert "隐藏社团" not in names


@pytest.mark.django_db
def test_public_list_supports_category_filter():
    """公开列表支持按类别筛选。"""
    from clubs.models import Club

    Club.objects.create(
        name="体育社团",
        category="体育竞技",
        introduction="简介",
        logo="logos/s1.png",
    )
    Club.objects.create(
        name="艺术社团",
        category="文化艺术",
        introduction="简介",
        logo="logos/s2.png",
    )
    client, _ = login_as_student()

    response = client.get("/api/clubs?category=体育竞技")

    body = response_body(response)
    names = [c["name"] for c in body["data"]["items"]]
    assert "体育社团" in names
    assert "艺术社团" not in names


@pytest.mark.django_db
def test_public_list_rejects_invalid_category():
    """非法的类别筛选返回 INVALID_CLUB_CATEGORY。"""
    client, _ = login_as_student()

    response = client.get("/api/clubs?category=不存在")

    assert response.status_code == 422
    assert response_body(response)["code"] == "INVALID_CLUB_CATEGORY"


@pytest.mark.django_db
def test_public_list_rejects_unauthenticated():
    """未登录不能查看公开社团列表。"""
    response = Client().get("/api/clubs")

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_public_list_accessible_by_admin():
    """管理员也可以访问公开社团列表。"""
    from clubs.models import Club

    Club.objects.create(
        name="管理员可看",
        category="其他",
        introduction="简介",
        logo="logos/a1.png",
    )
    client, _ = login_as_admin()

    response = client.get("/api/clubs")

    assert response.status_code == 200
    body = response_body(response)
    assert len(body["data"]["items"]) >= 1


# ── GET /api/clubs/{club_id} ──────────────────────────────────


@pytest.mark.django_db
def test_student_can_view_normal_club_detail():
    """学生可以查看正常社团详情。"""
    from clubs.models import Club

    club = Club.objects.create(
        name="详情测试社团",
        category="学术科技",
        introduction="详细介绍",
        logo="logos/d1.png",
    )
    client, _ = login_as_student()

    response = client.get(f"/api/clubs/{club.id}")

    assert response.status_code == 200
    body = response_body(response)
    assert body["data"]["name"] == "详情测试社团"
    assert body["data"]["introduction"] == "详细介绍"


@pytest.mark.django_db
def test_student_cannot_view_cancelled_club():
    """学生不能查看已注销社团（返回 RESOURCE_NOT_FOUND）。"""
    from clubs.models import Club

    club = Club.objects.create(
        name="已注销",
        category="其他",
        introduction="简介",
        logo="logos/c1.png",
        status=Club.Status.CANCELLED,
    )
    client, _ = login_as_student()

    response = client.get(f"/api/clubs/{club.id}")

    assert response.status_code == 404
    assert response_body(response)["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.django_db
def test_admin_can_view_cancelled_club():
    """管理员可以查看已注销社团详情。"""
    from clubs.models import Club

    club = Club.objects.create(
        name="管理员看已注销",
        category="其他",
        introduction="简介",
        logo="logos/a_cancel.png",
        status=Club.Status.CANCELLED,
    )
    client, _ = login_as_admin()

    response = client.get(f"/api/clubs/{club.id}")

    assert response.status_code == 200
    assert response_body(response)["data"]["status"] == "cancelled"


@pytest.mark.django_db
def test_club_detail_not_found():
    """不存在的社团返回 RESOURCE_NOT_FOUND。"""
    client, _ = login_as_student()

    response = client.get("/api/clubs/99999")

    assert response.status_code == 404
    assert response_body(response)["code"] == "RESOURCE_NOT_FOUND"


# ── GET /api/me/memberships ──────────────────────────────────


@pytest.mark.django_db
def test_my_memberships_shows_leader_role():
    """创建社团后，初始负责人能在"我的社团"看到负责人身份。"""
    from clubs.models import Club, ClubMembership

    leader = create_student(username="leader_me")
    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    club = Club.objects.create(
        name="我的负责人社团",
        category="学术科技",
        introduction="简介",
        logo="logos/m1.png",
    )
    ClubMembership.objects.create(
        user=leader,
        club=club,
        member_status=ClubMembership.MemberStatus.ACTIVE,
        club_role=ClubMembership.ClubRole.LEADER,
    )

    response = client.get("/api/me/memberships")

    assert response.status_code == 200
    body = response_body(response)
    items = body["data"]["items"]
    assert len(items) >= 1

    my_membership = next(
        (m for m in items if m["club"]["id"] == club.id), None
    )
    assert my_membership is not None
    assert my_membership["club_role"] == "leader"
    assert my_membership["member_status"] == "active"


@pytest.mark.django_db
def test_my_memberships_includes_history():
    """我的社团列表包含历史成员关系。"""
    from clubs.models import Club, ClubMembership

    student = create_student(username="history_student")
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    assert resp.status_code == 200

    club = Club.objects.create(
        name="历史社团",
        category="其他",
        introduction="简介",
        logo="logos/h1.png",
    )
    ClubMembership.objects.create(
        user=student,
        club=club,
        member_status=ClubMembership.MemberStatus.EXITED,
        club_role=ClubMembership.ClubRole.MEMBER,
    )

    response = client.get("/api/me/memberships")

    assert response.status_code == 200
    items = response_body(response)["data"]["items"]
    assert len(items) >= 1


@pytest.mark.django_db
def test_my_memberships_requires_student():
    """管理员不能访问我的社团接口。"""
    client, _ = login_as_admin()

    response = client.get("/api/me/memberships")

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_my_memberships_rejects_unauthenticated():
    """未登录不能访问我的社团。"""
    response = Client().get("/api/me/memberships")

    assert response.status_code == 401
    assert response_body(response)["code"] == "UNAUTHENTICATED"


# ── 负责人身份展示 ────────────────────────────────────────────


@pytest.mark.django_db
def test_leader_sees_leader_role_in_my_memberships():
    """通过 API 创建社团后，负责人能在"我的社团"看到 leader 身份。"""
    leader = create_student(username="api_leader", name="API负责人")
    client, _ = login_as_admin()

    #管理员创建社团
    logo = make_logo_file()
    logo.name = "l.png"

    resp = post_create_club(
        client,
        name="身份测试社团",
        category="公益实践",
        introduction="测试成员身份。",
        logo_file=logo,
        leader_ids=[leader.id],
    )
    assert resp.status_code == 201
    club_data = resp.json()["data"]["club"]

    #该负责人登录查看我的社团
    leader_client = Client()
    login_resp = login(leader_client, leader.username, "StrongPass!2026")
    assert login_resp.status_code == 200

    response = leader_client.get("/api/me/memberships")
    assert response.status_code == 200

    items = response_body(response)["data"]["items"]
    my_m = next((m for m in items if m["club"]["id"] == club_data["id"]), None)
    assert my_m is not None
    assert my_m["club_role"] == "leader"
    assert my_m["member_status"] == "active"
