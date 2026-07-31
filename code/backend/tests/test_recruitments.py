"""S06 招新发布与公开查看 — 后端测试。"""

import json
from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

LOGIN_URL = "/api/auth/login"


# ── 工具函数 ──────────────────────────────────────────────────

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
    return client.post(
        LOGIN_URL,
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login_as_admin():
    admin = create_admin()
    client = Client()
    resp = login(client, admin.username, "AdminPass!2026")
    assert resp.status_code == 200
    return client, admin


def login_as_student():
    student = create_student()
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    assert resp.status_code == 200
    return client, student


def create_test_club(name="测试社团", category="学术科技", introduction="简介", logo="logos/test.png", status=None):
    """创建一个测试社团。"""
    from clubs.models import Club

    kwargs = {
        "name": name,
        "category": category,
        "introduction": introduction,
        "logo": logo,
    }
    if status is not None:
        kwargs["status"] = status
    return Club.objects.create(**kwargs)


def create_test_membership(user, club, member_status="active", club_role="member"):
    """创建测试成员关系。"""
    from clubs.models import ClubMembership

    return ClubMembership.objects.create(
        user=user,
        club=club,
        member_status=member_status,
        club_role=club_role,
    )


def create_test_recruitment(club, publisher, **overrides):
    """创建一个测试招新。"""
    from clubs.models import Recruitment

    now = timezone.now()
    data = {
        "title": "测试招新",
        "introduction": "招新简介",
        "requirements": "招新要求",
        "capacity": 30,
        "start_time": now - timedelta(days=1),
        "end_time": now + timedelta(days=30),
        "club": club,
        "publisher": publisher,
        **overrides,
    }
    return Recruitment.objects.create(**data)


# ═══════════════════════════════════════════════════════════════
# 公开列表 GET /api/clubs/{club_id}/recruitments
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_public_list_recruitments():
    """学生可以看到正常社团的未结束招新。"""
    leader = create_student(username="pub_leader", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader)

    client, _ = login_as_student()
    response = client.get(f"/api/clubs/{club.id}/recruitments")

    assert response.status_code == 200
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    items = body["data"]["items"]
    assert len(items) >= 1
    rec = items[0]
    assert rec["title"] == "测试招新"
    assert rec["display_status"] == "进行中"
    assert rec["approved_count"] == 0
    assert "publisher" in rec


@pytest.mark.django_db
def test_public_list_excludes_ended_early():
    """学生列表不显示已提前结束的招新。"""
    leader = create_student(username="early_end_pub", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader, ended_early=True)

    client, _ = login_as_student()
    response = client.get(f"/api/clubs/{club.id}/recruitments")

    assert response.status_code == 200
    items = response_body(response)["data"]["items"]
    assert len(items) == 0


@pytest.mark.django_db
def test_public_list_excludes_past_end_time():
    """学生列表不显示已到期结束的招新。"""
    leader = create_student(username="past_end_pub", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    past = timezone.now() - timedelta(days=10)
    create_test_recruitment(club, leader, end_time=past)

    client, _ = login_as_student()
    response = client.get(f"/api/clubs/{club.id}/recruitments")

    items = response_body(response)["data"]["items"]
    assert len(items) == 0


@pytest.mark.django_db
def test_public_list_excludes_cancelled_club():
    """已注销社团的招新不公开。"""
    leader = create_student(username="cancelled_club_pub", name="负责")
    club = create_test_club(status="cancelled")
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader)

    client, _ = login_as_student()
    response = client.get(f"/api/clubs/{club.id}/recruitments")

    #非管理员看已注销社团应该返回 404
    assert response.status_code == 404


@pytest.mark.django_db
def test_public_list_admin_can_see_cancelled_club_recruitments():
    """管理员可以查看已注销社团的招新。"""
    leader = create_student(username="admin_cancelled_pub", name="负责")
    club = create_test_club(status="cancelled")
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader)

    client, _ = login_as_admin()
    response = client.get(f"/api/clubs/{club.id}/recruitments")

    assert response.status_code == 200
    #管理员也能看到招新（但公开列表过滤未结束，所以不会显示已结束）
    #已注销社团的招新可能已结束也可能未结束，此测试确认管理员有权访问
    assert response_body(response)["code"] == "SUCCESS"


@pytest.mark.django_db
def test_public_list_display_status_not_started():
    """未开始招新的 display_status 为 '未开始'。"""
    leader = create_student(username="not_start_pub", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    future = timezone.now() + timedelta(days=30)
    create_test_recruitment(club, leader, start_time=future, end_time=future + timedelta(days=30))

    client, _ = login_as_student()
    response = client.get(f"/api/clubs/{club.id}/recruitments")

    items = response_body(response)["data"]["items"]
    assert len(items) == 1
    assert items[0]["display_status"] == "未开始"


@pytest.mark.django_db
def test_public_list_pagination():
    """公开招新列表支持分页。"""
    leader = create_student(username="page_pub", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    for i in range(5):
        create_test_recruitment(club, leader, title=f"招新{i}")

    client, _ = login_as_student()
    response = client.get(f"/api/clubs/{club.id}/recruitments?page=1&page_size=2")

    body = response_body(response)
    assert len(body["data"]["items"]) <= 2
    assert body["data"]["total"] >= 5


@pytest.mark.django_db
def test_public_list_requires_auth():
    """未登录不能查看招新列表。"""
    leader = create_student(username="auth_required", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader)

    response = Client().get(f"/api/clubs/{club.id}/recruitments")
    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════
# 负责人创建 POST /api/leader/clubs/{club_id}/recruitments
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_leader_create_recruitment():
    """负责人可以发布招新。"""
    leader = create_student(username="create_leader", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    now = timezone.now()
    start = (now + timedelta(days=1)).isoformat()
    end = (now + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "2026秋季招新",
            "introduction": "欢迎加入",
            "requirements": "热爱技术",
            "capacity": 50,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response_body(response)
    assert body["code"] == "SUCCESS"
    assert body["data"]["title"] == "2026秋季招新"
    assert body["data"]["capacity"] == 50
    assert body["data"]["publisher"]["id"] == leader.id
    assert body["data"]["publisher"]["username"] == leader.username


@pytest.mark.django_db
def test_leader_create_rejects_missing_title():
    """标题为空不能发布招新。"""
    leader = create_student(username="no_title", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_leader_create_rejects_title_too_long():
    """标题超过 200 字返回 VALIDATION_ERROR。"""
    leader = create_student(username="long_title", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "A" * 201,
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_leader_create_rejects_invalid_capacity():
    """人数 <= 0 返回 INVALID_CAPACITY。"""
    leader = create_student(username="bad_cap", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "招新",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 0,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "INVALID_CAPACITY"


@pytest.mark.django_db
def test_leader_create_rejects_invalid_time_range():
    """开始时间 >= 结束时间返回 INVALID_TIME_RANGE。"""
    leader = create_student(username="bad_time", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    now = timezone.now()
    t = (now + timedelta(days=1)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "招新",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": t,
            "end_time": t,
        }),
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response_body(response)["code"] == "INVALID_TIME_RANGE"


@pytest.mark.django_db
def test_leader_create_rejects_non_leader():
    """非负责人不能发布招新。"""
    member = create_student(username="not_leader_create", name="普通")
    club = create_test_club()
    create_test_membership(member, club, member_status="active", club_role="member")

    client = Client()
    resp = login(client, member.username, "StrongPass!2026")
    assert resp.status_code == 200

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "招新",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "NOT_CLUB_LEADER"


@pytest.mark.django_db
def test_leader_create_rejects_cancelled_club():
    """已注销社团不能发布招新。"""
    leader = create_student(username="cancelled_create", name="负责")
    club = create_test_club(status="cancelled")
    create_test_membership(leader, club, member_status="active", club_role="leader")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "招新",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response_body(response)["code"] == "CLUB_CANCELLED"


@pytest.mark.django_db
def test_leader_create_rejects_unauthenticated():
    """未登录不能发布招新。"""
    leader = create_student(username="unauth_create", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = Client().post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "招新",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_leader_create_rejects_admin():
    """管理员不能发布招新。"""
    club = create_test_club()
    client, _ = login_as_admin()

    start = (timezone.now() + timedelta(days=1)).isoformat()
    end = (timezone.now() + timedelta(days=30)).isoformat()

    response = client.post(
        f"/api/leader/clubs/{club.id}/recruitments",
        data=json.dumps({
            "title": "招新",
            "introduction": "欢迎",
            "requirements": "要求",
            "capacity": 30,
            "start_time": start,
            "end_time": end,
        }),
        content_type="application/json",
    )

    assert response.status_code == 403


# ═══════════════════════════════════════════════════════════════
# 负责人列表 GET /api/leader/clubs/{club_id}/recruitments
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_leader_list_all_recruitments():
    """负责人可以查看全部招新（含已结束）。"""
    leader = create_student(username="leader_list_all", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader, title="进行中")
    create_test_recruitment(club, leader, title="已结束", ended_early=True)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")

    assert response.status_code == 200
    items = response_body(response)["data"]["items"]
    assert len(items) == 2
    titles = {r["title"] for r in items}
    assert "进行中" in titles
    assert "已结束" in titles


@pytest.mark.django_db
def test_leader_list_rejects_non_leader():
    """非负责人不能查看全部招新列表。"""
    member = create_student(username="member_list", name="普通")
    club = create_test_club()
    create_test_membership(member, club, member_status="active", club_role="member")

    client = Client()
    resp = login(client, member.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")
    assert response.status_code == 403
    assert response_body(response)["code"] == "NOT_CLUB_LEADER"


# ═══════════════════════════════════════════════════════════════
# 负责人修改 PATCH /api/leader/recruitments/{recruitment_id}
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_leader_update_recruitment():
    """负责人可以修改未结束的招新。"""
    leader = create_student(username="update_leader", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader, title="旧标题")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"title": "新标题", "capacity": 60}),
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response_body(response)
    assert body["data"]["title"] == "新标题"
    assert body["data"]["capacity"] == 60
    r.refresh_from_db()
    assert r.title == "新标题"
    assert r.capacity == 60


@pytest.mark.django_db
def test_leader_update_rejects_ended_early():
    """已提前结束的招新不能修改。"""
    leader = create_student(username="ended_update", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader, ended_early=True)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"title": "改"}),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response_body(response)["code"] == "RECRUITMENT_ENDED"


@pytest.mark.django_db
def test_leader_update_rejects_past_end_time():
    """已到期结束的招新不能修改。"""
    leader = create_student(username="past_update", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    past = timezone.now() - timedelta(days=1)
    r = create_test_recruitment(club, leader, end_time=past)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"title": "改"}),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response_body(response)["code"] == "RECRUITMENT_ENDED"


@pytest.mark.django_db
def test_leader_update_rejects_empty_body():
    """空请求体不能修改。"""
    leader = create_student(username="empty_update", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_leader_update_rejects_other_club_leader():
    """其他社团负责人不能修改招新。"""
    leader1 = create_student(username="owner_leader", name="负责1")
    leader2 = create_student(username="other_leader", name="负责2")
    club1 = create_test_club(name="社团1")
    club2 = create_test_club(name="社团2")
    create_test_membership(leader1, club1, member_status="active", club_role="leader")
    create_test_membership(leader2, club2, member_status="active", club_role="leader")
    r = create_test_recruitment(club1, leader1)

    client = Client()
    resp = login(client, leader2.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"title": "篡改"}),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response_body(response)["code"] == "NOT_CLUB_LEADER"


@pytest.mark.django_db
def test_leader_update_rejects_forbidden_field():
    """不允许修改未知字段。"""
    leader = create_student(username="forbidden_field", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"club_id": 999, "title": "改"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response_body(response)["code"] == "INVALID_REQUEST"


@pytest.mark.django_db
def test_leader_update_can_modify_introduction():
    """负责人可以修改招新简介。"""
    leader = create_student(username="intro_update", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader, introduction="旧简介")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"introduction": "新简介"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["introduction"] == "新简介"


@pytest.mark.django_db
def test_leader_update_can_modify_requirements():
    """负责人可以修改招新要求。"""
    leader = create_student(username="req_update", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader, requirements="旧要求")

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"requirements": "新要求"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["requirements"] == "新要求"


@pytest.mark.django_db
def test_leader_update_can_modify_start_time():
    """负责人可以修改开始时间。"""
    leader = create_student(username="start_update", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    now = timezone.now()
    r = create_test_recruitment(club, leader, start_time=now, end_time=now + timedelta(days=30))

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    new_start = (now + timedelta(days=1)).isoformat()
    response = client.patch(
        f"/api/leader/recruitments/{r.id}",
        data=json.dumps({"start_time": new_start}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response_body(response)["data"]["display_status"] == "未开始"


# ═══════════════════════════════════════════════════════════════
# 提前结束 POST /api/leader/recruitments/{recruitment_id}/end
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_leader_end_recruitment():
    """负责人可以提前结束招新。"""
    leader = create_student(username="end_leader", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.post(f"/api/leader/recruitments/{r.id}/end")

    assert response.status_code == 200
    body = response_body(response)
    assert body["data"]["ended_early"] is True
    assert body["data"]["display_status"] == "已结束"
    r.refresh_from_db()
    assert r.ended_early is True


@pytest.mark.django_db
def test_leader_end_already_ended_early():
    """已提前结束的招新不能重复结束。"""
    leader = create_student(username="double_end", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    r = create_test_recruitment(club, leader, ended_early=True)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.post(f"/api/leader/recruitments/{r.id}/end")

    assert response.status_code == 409
    assert response_body(response)["code"] == "RECRUITMENT_ENDED"


@pytest.mark.django_db
def test_leader_end_already_past_end_time():
    """已到期结束的招新不能提前结束。"""
    leader = create_student(username="past_end", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    past = timezone.now() - timedelta(days=1)
    r = create_test_recruitment(club, leader, end_time=past)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.post(f"/api/leader/recruitments/{r.id}/end")

    assert response.status_code == 409
    assert response_body(response)["code"] == "RECRUITMENT_ENDED"


@pytest.mark.django_db
def test_leader_end_rejects_other_club_leader():
    """其他社团负责人不能提前结束招新。"""
    leader1 = create_student(username="end_owner", name="负责1")
    leader2 = create_student(username="end_other", name="负责2")
    club1 = create_test_club(name="社团A")
    club2 = create_test_club(name="社团B")
    create_test_membership(leader1, club1, member_status="active", club_role="leader")
    create_test_membership(leader2, club2, member_status="active", club_role="leader")
    r = create_test_recruitment(club1, leader1)

    client = Client()
    resp = login(client, leader2.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.post(f"/api/leader/recruitments/{r.id}/end")

    assert response.status_code == 403
    assert response_body(response)["code"] == "NOT_CLUB_LEADER"


# ═══════════════════════════════════════════════════════════════
# 管理员列表 GET /api/admin/recruitments
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_admin_list_all_recruitments():
    """管理员可以查看全量招新记录。"""
    leader = create_student(username="admin_all", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader, title="进行中")
    create_test_recruitment(club, leader, title="已结束", ended_early=True)

    client, _ = login_as_admin()
    response = client.get("/api/admin/recruitments")

    assert response.status_code == 200
    items = response_body(response)["data"]["items"]
    assert len(items) >= 2


@pytest.mark.django_db
def test_admin_list_includes_cancelled_club():
    """管理员列表包含已注销社团的招新。"""
    leader = create_student(username="admin_cancelled", name="负责")
    club = create_test_club(status="cancelled")
    create_test_membership(leader, club, member_status="active", club_role="leader")
    create_test_recruitment(club, leader, title="注销社团招新")

    client, _ = login_as_admin()
    response = client.get("/api/admin/recruitments")

    items = response_body(response)["data"]["items"]
    titles = {r["title"] for r in items}
    assert "注销社团招新" in titles


@pytest.mark.django_db
def test_admin_list_pagination():
    """管理员招新列表分页正确。"""
    leader = create_student(username="admin_page", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    for i in range(5):
        create_test_recruitment(club, leader, title=f"招新{i}")

    client, _ = login_as_admin()
    response = client.get("/api/admin/recruitments?page=1&page_size=2")

    body = response_body(response)
    assert len(body["data"]["items"]) <= 2
    assert body["data"]["total"] >= 5


@pytest.mark.django_db
def test_admin_list_rejects_student():
    """学生不能访问管理员招新列表。"""
    client, _ = login_as_student()
    response = client.get("/api/admin/recruitments")

    assert response.status_code == 403
    assert response_body(response)["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_admin_list_rejects_unauthenticated():
    """未登录不能访问管理员招新列表。"""
    response = Client().get("/api/admin/recruitments")
    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════
# display_status 计算逻辑
# ═══════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_display_status_not_started():
    """当前时间 < start_time → 未开始。"""
    leader = create_student(username="ds_not_start", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    future = timezone.now() + timedelta(days=10)
    r = create_test_recruitment(club, leader, start_time=future, end_time=future + timedelta(days=30))

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")
    item = response_body(response)["data"]["items"][0]
    assert item["display_status"] == "未开始"


@pytest.mark.django_db
def test_display_status_in_progress():
    """在时间窗口内 → 进行中。"""
    leader = create_student(username="ds_progress", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    now = timezone.now()
    r = create_test_recruitment(club, leader, start_time=now - timedelta(days=1), end_time=now + timedelta(days=30))

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")
    item = response_body(response)["data"]["items"][0]
    assert item["display_status"] == "进行中"


@pytest.mark.django_db
def test_display_status_ended_by_early():
    """ended_early=True → 已结束（优先于已满）。"""
    leader = create_student(username="ds_early", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    now = timezone.now()
    r = create_test_recruitment(
        club, leader,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=30),
        ended_early=True,
    )

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")
    item = response_body(response)["data"]["items"][0]
    assert item["display_status"] == "已结束"


@pytest.mark.django_db
def test_display_status_ended_by_time():
    """now >= end_time → 已结束。"""
    leader = create_student(username="ds_time_end", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    past_start = timezone.now() - timedelta(days=30)
    past_end = timezone.now() - timedelta(days=1)
    r = create_test_recruitment(club, leader, start_time=past_start, end_time=past_end)

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")
    item = response_body(response)["data"]["items"][0]
    assert item["display_status"] == "已结束"


@pytest.mark.django_db
def test_display_status_ended_outranks_full():
    """已结束的优先级高于已满（即使已满，已结束后仍显示已结束）。"""
    leader = create_student(username="ds_ended_over_full", name="负责")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    now = timezone.now()
    r = create_test_recruitment(
        club, leader,
        start_time=now - timedelta(days=2),
        end_time=now - timedelta(days=1),
    )

    #S06 中没有 join_application，所以 approved_count 总是 0
    #但即使未来 S07 有已通过申请人，已结束后仍应显示已结束
    #此测试主要验证已结束的状态在时间到期后正确计算

    client = Client()
    resp = login(client, leader.username, "StrongPass!2026")
    assert resp.status_code == 200

    response = client.get(f"/api/leader/clubs/{club.id}/recruitments")
    item = response_body(response)["data"]["items"][0]
    assert item["display_status"] == "已结束"
