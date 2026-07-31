"""S10 帖子发布、列表、详情与置顶 — 后端测试。"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/auth/login"


# ── 工具函数 ──────────────────────────────────────────────────

def response_body(response):
    return json.loads(response.content)


def create_student(**overrides):
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


def login_as_student(username="test_student"):
    student = create_student(username=username)
    client = Client()
    resp = login(client, student.username, "StrongPass!2026")
    assert resp.status_code == 200
    return client, student


def create_test_club(name="测试社团", category="学术科技", introduction="简介", logo="logos/test.png"):
    from clubs.models import Club

    return Club.objects.create(
        name=name,
        category=category,
        introduction=introduction,
        logo=logo,
    )


def create_test_membership(user, club, member_status="active", club_role="member"):
    from clubs.models import ClubMembership

    return ClubMembership.objects.create(
        user=user,
        club=club,
        member_status=member_status,
        club_role=club_role,
    )


def create_post(club, author, title="测试帖子", content="帖子内容", is_pinned=False):
    from clubs.models import Post

    return Post.objects.create(
        title=title,
        content=content,
        club=club,
        author=author,
        is_pinned=is_pinned,
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/clubs/{club_id}/posts — 成员查看帖子列表
# ═══════════════════════════════════════════════════════════════


def test_member_list_posts_success():
    """在社成员成功查看正常帖子，置顶优先，同组按 ID 倒序。"""
    client, student = login_as_student()
    member2 = create_student(username="member_01")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(member2, club, member_status="active", club_role="member")

    #创建帖子（先普通，后置顶）
    p1 = create_post(club, student, title="普通帖子1")
    p2 = create_post(club, member2, title="普通帖子2")
    p3 = create_post(club, student, title="置顶帖子", is_pinned=True)

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 3
    items = body["data"]["items"]
    #置顶帖子应在最前面
    assert items[0]["id"] == p3.id
    assert items[0]["is_pinned"] is True
    #同组按 ID 倒序（p2.id > p1.id）
    assert items[1]["id"] == p2.id
    assert items[2]["id"] == p1.id


def test_member_list_posts_author_info():
    """帖子列表包含正确的作者信息。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_post(club, student, title="我的帖子")

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    item = body["data"]["items"][0]
    assert item["author"]["id"] == student.id
    assert item["author"]["username"] == student.username


def test_member_list_posts_has_like_fields():
    """帖子列表返回 like_count 和 liked_by_me 字段（S10 预置值）。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_post(club, student)

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    item = body["data"]["items"][0]
    assert item["like_count"] == 0
    assert item["liked_by_me"] is False


def test_member_list_posts_excludes_deleted():
    """成员查看不包括已删除帖子。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    from clubs.models import Post

    create_post(club, student, title="正常帖子")
    p2 = create_post(club, student, title="已删除帖子")
    p2.status = Post.Status.DELETED
    p2.save()

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["title"] == "正常帖子"


def test_member_list_posts_empty():
    """无帖子时返回空列表。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_member_list_posts_non_member_rejected():
    """非社团成员不能查看帖子。"""
    client, student = login_as_student()
    club = create_test_club()
    #student 不是该社团成员

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_MEMBER"


def test_member_list_posts_ex_member_rejected():
    """已退出成员不能查看帖子。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="exited", club_role="member")

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_member_list_posts_cancelled_club_rejected():
    """已注销社团成员不能查看帖子。"""
    client, student = login_as_student()
    from clubs.models import Club

    club = Club.objects.create(
        name="已注销社团",
        category="学术科技",
        introduction="简介",
        logo="logos/test.png",
        status=Club.Status.CANCELLED,
    )
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "CLUB_CANCELLED"


def test_member_list_posts_unauthenticated_rejected():
    """未登录不能查看帖子。"""
    club = create_test_club()
    client = Client()

    resp = client.get(f"/api/clubs/{club.id}/posts")

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


def test_member_list_posts_pagination():
    """帖子列表支持分页。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    for i in range(5):
        create_post(club, student, title=f"帖子{i}")

    resp = client.get(f"/api/clubs/{club.id}/posts?page=1&page_size=2")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    assert body["data"]["total"] == 5
    assert len(body["data"]["items"]) == 2


# ═══════════════════════════════════════════════════════════════
# GET /api/posts/{post_id} — 帖子详情
# ═══════════════════════════════════════════════════════════════


def test_post_detail_success():
    """在社成员成功查看帖子详情。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student, title="详情帖子", content="详细内容")

    resp = client.get(f"/api/posts/{post.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["id"] == post.id
    assert body["data"]["title"] == "详情帖子"
    assert body["data"]["content"] == "详细内容"
    assert body["data"]["author"]["username"] == student.username
    assert body["data"]["is_pinned"] is False
    assert body["data"]["status"] == "正常"


def test_post_detail_nonexistent():
    """查看不存在的帖子返回 404。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.get("/api/posts/99999")

    assert resp.status_code == 404
    body = response_body(resp)
    assert body["code"] == "RESOURCE_NOT_FOUND"


def test_post_detail_deleted_rejected():
    """已删除帖子对普通成员不可见。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)
    from clubs.models import Post

    post.status = Post.Status.DELETED
    post.save()

    resp = client.get(f"/api/posts/{post.id}")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "RESOURCE_DELETED"


def test_post_detail_non_member_rejected():
    """非成员不能查看帖子详情。"""
    client, student = login_as_student()
    club = create_test_club()
    author = create_student(username="author_01")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    #当前学生不是该社团成员

    resp = client.get(f"/api/posts/{post.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_MEMBER"


def test_post_detail_unauthenticated_rejected():
    """未登录不能查看帖子详情。"""
    club = create_test_club()
    author = create_student(username="author_02")
    post = create_post(club, author)
    client = Client()

    resp = client.get(f"/api/posts/{post.id}")

    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# POST /api/clubs/{club_id}/posts — 成员发布帖子
# ═══════════════════════════════════════════════════════════════


def test_member_create_post_success():
    """在社成员成功发布帖子。"""
    client, student = login_as_student("poster_01")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({
            "title": "新帖子标题",
            "content": "帖子正文内容",
        }),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["title"] == "新帖子标题"
    assert body["data"]["content"] == "帖子正文内容"
    assert body["data"]["is_pinned"] is False
    assert body["data"]["status"] == "正常"
    assert body["data"]["author"]["id"] == student.id
    assert body["data"]["like_count"] == 0
    assert body["data"]["liked_by_me"] is False


def test_member_create_post_leader_can_post():
    """负责人也可以在社发布帖子。"""
    client, leader = login_as_student("leader_poster")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({
            "title": "负责人帖子",
            "content": "负责人发布的内容",
        }),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["data"]["title"] == "负责人帖子"


def test_member_create_post_empty_title_rejected():
    """标题为空拒绝。"""
    client, student = login_as_student("poster_02")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "", "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_member_create_post_empty_content_rejected():
    """内容为空拒绝。"""
    client, student = login_as_student("poster_03")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "标题", "content": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_member_create_post_title_too_long():
    """标题超过 255 字拒绝。"""
    client, student = login_as_student("poster_04")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "A" * 256, "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 422
    body = response_body(resp)
    assert body["code"] == "VALIDATION_ERROR"


def test_member_create_post_content_too_long():
    """内容超过 5000 字拒绝。"""
    client, student = login_as_student("poster_05")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "标题", "content": "C" * 5001}),
        content_type="application/json",
    )

    assert resp.status_code == 422
    body = response_body(resp)
    assert body["code"] == "VALIDATION_ERROR"


def test_member_create_post_rejects_is_pinned():
    """发布帖子时不允许提交 is_pinned 字段。"""
    client, student = login_as_student("poster_06")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "标题", "content": "内容", "is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_member_create_post_rejects_status():
    """发布帖子时不允许提交 status 字段。"""
    client, student = login_as_student("poster_07")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "标题", "content": "内容", "status": "正常"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_member_create_post_non_member_rejected():
    """非社团成员不能发布帖子。"""
    client, student = login_as_student("poster_08")
    club = create_test_club()
    #student 不是该社团成员

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "标题", "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_MEMBER"


def test_member_create_post_unauthenticated_rejected():
    """未登录不能发布帖子。"""
    club = create_test_club()
    client = Client()

    resp = client.post(
        f"/api/clubs/{club.id}/posts",
        data=json.dumps({"title": "标题", "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# PATCH /api/leader/posts/{post_id}/pin — 负责人置顶帖子
# ═══════════════════════════════════════════════════════════════


def test_leader_pin_post_success():
    """负责人成功置顶帖子。"""
    client, leader = login_as_student("leader_10")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    member = create_student(username="member_10")
    create_test_membership(member, club, member_status="active", club_role="member")
    post = create_post(club, member, is_pinned=False)

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["is_pinned"] is True


def test_leader_unpin_post_success():
    """负责人成功取消置顶帖子。"""
    client, leader = login_as_student("leader_11")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    post = create_post(club, leader, is_pinned=True)

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": False}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["is_pinned"] is False


def test_leader_pin_deleted_post_rejected():
    """已删除帖子不能置顶。"""
    client, leader = login_as_student("leader_12")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    post = create_post(club, leader)
    from clubs.models import Post

    post.status = Post.Status.DELETED
    post.save()

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "POST_DELETED"


def test_leader_pin_post_other_club_rejected():
    """不能置顶其他社团的帖子。"""
    client, leader = login_as_student("leader_13")
    club_a = create_test_club(name="社团A")
    club_b = create_test_club(name="社团B")
    create_test_membership(leader, club_a, member_status="active", club_role="leader")
    other_member = create_student(username="other_member")
    create_test_membership(other_member, club_b, member_status="active", club_role="member")
    post = create_post(club_b, other_member)

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_pin_post_non_leader_rejected():
    """普通成员不能置顶帖子。"""
    client, student = login_as_student("member_14")
    leader = create_student(username="leader_14")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(leader, club, member_status="active", club_role="leader")
    post = create_post(club, student)

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_pin_post_missing_field():
    """缺少 is_pinned 字段拒绝。"""
    client, leader = login_as_student("leader_15")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    post = create_post(club, leader)

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_leader_pin_post_nonexistent():
    """置顶不存在的帖子返回 404。"""
    client, leader = login_as_student("leader_16")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.patch(
        "/api/leader/posts/99999/pin",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 404


def test_leader_pin_post_unauthenticated_rejected():
    """未登录不能置顶帖子。"""
    club = create_test_club()
    author = create_student(username="author_17")
    post = create_post(club, author)
    client = Client()

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 401


def test_leader_pin_post_rejects_other_fields():
    """置顶接口拒绝 is_pinned 之外的其他字段。"""
    client, leader = login_as_student("leader_18")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    post = create_post(club, leader)

    resp = client.patch(
        f"/api/leader/posts/{post.id}/pin",
        data=json.dumps({"is_pinned": True, "title": "篡改标题"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"
