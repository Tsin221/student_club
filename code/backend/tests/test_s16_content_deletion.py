"""S16 内容逻辑删除和管理员内容管理 — 后端测试。"""

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


def create_reply(post, author, content="回复内容"):
    from clubs.models import Reply

    return Reply.objects.create(
        content=content,
        post=post,
        author=author,
    )


# ═══════════════════════════════════════════════════════════════
# DELETE /api/posts/{post_id} — 逻辑删除帖子
# ═══════════════════════════════════════════════════════════════


def test_author_delete_own_post_success():
    """作者（仍在社）成功删除本人帖子。"""
    client, author = login_as_student("post_author")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["id"] == post.id
    assert body["data"]["status"] == "已删除"

    # 数据库验证
    from clubs.models import Post
    post.refresh_from_db()
    assert post.status == Post.Status.DELETED


def test_author_delete_post_exited_member_rejected():
    """作者已退出社团时不能删除帖子。"""
    client, author = login_as_student("exited_author")
    club = create_test_club()
    create_test_membership(author, club, member_status="exited", club_role="member")
    post = create_post(club, author)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_author_delete_post_not_member_rejected():
    """作者从未加入社团时不能删除帖子。"""
    client, author = login_as_student("non_member_author")
    club = create_test_club()
    post = create_post(club, author)
    # 作者曾经是成员但现在完全不是

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_delete_post_already_deleted_rejected():
    """重复删除已删除帖子返回 POST_DELETED。"""
    client, author = login_as_student("dup_del_author")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    from clubs.models import Post
    post.status = Post.Status.DELETED
    post.save()

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "POST_DELETED"


def test_leader_delete_club_post_success():
    """负责人成功删除本社团帖子。"""
    client, leader = login_as_student("leader_deleter")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    member = create_student(username="post_member")
    create_test_membership(member, club, member_status="active", club_role="member")
    post = create_post(club, member)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已删除"


def test_leader_delete_other_club_post_rejected():
    """负责人不能删除其他社团帖子。"""
    client, leader = login_as_student("other_club_leader")
    club_a = create_test_club(name="社团A")
    club_b = create_test_club(name="社团B")
    create_test_membership(leader, club_a, member_status="active", club_role="leader")
    other_member = create_student(username="other_member")
    create_test_membership(other_member, club_b, member_status="active", club_role="member")
    post = create_post(club_b, other_member)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_admin_delete_any_post_success():
    """管理员可以删除任意帖子。"""
    client, admin = login_as_admin()
    club = create_test_club()
    author = create_student(username="any_author")
    post = create_post(club, author)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已删除"


def test_unauthenticated_delete_post_rejected():
    """未登录不能删除帖子。"""
    club = create_test_club()
    author = create_student(username="unauth_author")
    post = create_post(club, author)
    client = Client()

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


def test_random_user_delete_post_rejected():
    """非作者、非负责人、非管理员的普通成员不能删除他人的帖子。"""
    client, random_user = login_as_student("random_user")
    club = create_test_club()
    create_test_membership(random_user, club, member_status="active", club_role="member")
    author = create_student(username="the_author")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "FORBIDDEN"


def test_delete_post_nonexistent():
    """删除不存在帖子返回 404。"""
    client, student = login_as_student("no_post_user")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.delete("/api/posts/99999")

    assert resp.status_code == 404
    body = response_body(resp)
    assert body["code"] == "RESOURCE_NOT_FOUND"


def test_delete_post_cancelled_club_rejected():
    """社团已注销时作者不能删除帖子。"""
    client, author = login_as_student("cancelled_author")
    from clubs.models import Club

    club = Club.objects.create(
        name="已注销社团",
        category="学术科技",
        introduction="简介",
        logo="logos/test.png",
        status=Club.Status.CANCELLED,
    )
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)

    resp = client.delete(f"/api/posts/{post.id}")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "CLUB_CANCELLED"


# ═══════════════════════════════════════════════════════════════
# DELETE /api/replies/{reply_id} — 逻辑删除回复
# ═══════════════════════════════════════════════════════════════


def test_author_delete_own_reply_success():
    """作者（仍在社，父帖未删除）成功删除本人回复。"""
    client, author = login_as_student("reply_author")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    reply = create_reply(post, author)

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["id"] == reply.id
    assert body["data"]["status"] == "已删除"

    # 数据库验证
    from clubs.models import Reply
    reply.refresh_from_db()
    assert reply.status == Reply.Status.DELETED


def test_author_delete_reply_parent_post_deleted_rejected():
    """父帖已删除时作者不能删除回复。"""
    client, author = login_as_student("parent_del_author")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    reply = create_reply(post, author)
    from clubs.models import Post
    post.status = Post.Status.DELETED
    post.save()

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "POST_DELETED"


def test_delete_reply_already_deleted_rejected():
    """重复删除已删除回复返回 REPLY_DELETED。"""
    client, author = login_as_student("dup_reply_author")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    reply = create_reply(post, author)
    from clubs.models import Reply
    reply.status = Reply.Status.DELETED
    reply.save()

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "REPLY_DELETED"


def test_author_delete_reply_exited_member_rejected():
    """作者已退出社团时不能删除回复。"""
    client, author = login_as_student("exited_replier")
    club = create_test_club()
    create_test_membership(author, club, member_status="exited", club_role="member")
    post = create_post(club, author)
    reply = create_reply(post, author)

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_leader_delete_club_reply_success():
    """负责人成功删除本社团回复。"""
    client, leader = login_as_student("reply_leader")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    member = create_student(username="reply_member")
    create_test_membership(member, club, member_status="active", club_role="member")
    post = create_post(club, member)
    reply = create_reply(post, member)

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已删除"


def test_admin_delete_any_reply_success():
    """管理员可以删除任意回复。"""
    client, admin = login_as_admin()
    club = create_test_club()
    author = create_student(username="any_replier")
    post = create_post(club, author)
    reply = create_reply(post, author)

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已删除"


def test_unauthenticated_delete_reply_rejected():
    """未登录不能删除回复。"""
    club = create_test_club()
    author = create_student(username="unauth_replier")
    post = create_post(club, author)
    reply = create_reply(post, author)
    client = Client()

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


def test_random_user_delete_reply_rejected():
    """非作者、非负责人、非管理员的普通成员不能删除他人的回复。"""
    client, random_user = login_as_student("random_replier")
    club = create_test_club()
    create_test_membership(random_user, club, member_status="active", club_role="member")
    author = create_student(username="reply_owner")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    reply = create_reply(post, author)

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "FORBIDDEN"


def test_delete_reply_nonexistent():
    """删除不存在回复返回 404。"""
    client, student = login_as_student("no_reply_user")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.delete("/api/replies/99999")

    assert resp.status_code == 404
    body = response_body(resp)
    assert body["code"] == "RESOURCE_NOT_FOUND"


def test_leader_delete_reply_wrong_club_rejected():
    """负责人不能删除其他社团的回复。"""
    client, leader = login_as_student("wrong_club_leader")
    club_a = create_test_club(name="社团A")
    club_b = create_test_club(name="社团B")
    create_test_membership(leader, club_a, member_status="active", club_role="leader")
    other_member = create_student(username="b_member")
    create_test_membership(other_member, club_b, member_status="active", club_role="member")
    post = create_post(club_b, other_member)
    reply = create_reply(post, other_member)

    resp = client.delete(f"/api/replies/{reply.id}")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


# ═══════════════════════════════════════════════════════════════
# GET /api/admin/posts — 管理员查看全部帖子
# ═══════════════════════════════════════════════════════════════


def test_admin_list_all_posts_includes_deleted():
    """管理员列表包含已删除帖子。"""
    client, admin = login_as_admin()
    club = create_test_club()
    author = create_student(username="admin_posts_author")
    create_test_membership(author, club, member_status="active", club_role="member")
    from clubs.models import Post

    p1 = create_post(club, author, title="正常帖子")
    p2 = create_post(club, author, title="已删除帖子")
    p2.status = Post.Status.DELETED
    p2.save()

    resp = client.get("/api/admin/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 2
    statuses = [item["status"] for item in body["data"]["items"]]
    assert "正常" in statuses
    assert "已删除" in statuses


def test_admin_list_posts_pagination():
    """管理员帖子列表支持分页。"""
    client, admin = login_as_admin()
    club = create_test_club()
    author = create_student(username="pag_posts_author")
    create_test_membership(author, club, member_status="active", club_role="member")

    for i in range(5):
        create_post(club, author, title=f"帖子{i}")

    resp = client.get("/api/admin/posts?page=1&page_size=2")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    assert body["data"]["total"] == 5
    assert len(body["data"]["items"]) == 2


def test_admin_list_posts_non_admin_rejected():
    """非管理员不能查看管理员帖子列表。"""
    client, student = login_as_student("non_admin_posts")

    resp = client.get("/api/admin/posts")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "FORBIDDEN"


def test_admin_list_posts_empty():
    """无帖子时返回空列表。"""
    client, admin = login_as_admin()

    resp = client.get("/api/admin/posts")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_admin_list_posts_unauthenticated_rejected():
    """未登录不能查看管理员帖子列表。"""
    client = Client()

    resp = client.get("/api/admin/posts")

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


# ═══════════════════════════════════════════════════════════════
# GET /api/admin/replies — 管理员查看全部回复
# ═══════════════════════════════════════════════════════════════


def test_admin_list_all_replies_includes_deleted():
    """管理员回复列表包含已删除回复。"""
    client, admin = login_as_admin()
    club = create_test_club()
    author = create_student(username="admin_replies_author")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)
    from clubs.models import Reply

    r1 = create_reply(post, author, content="正常回复")
    r2 = create_reply(post, author, content="已删除回复")
    r2.status = Reply.Status.DELETED
    r2.save()

    resp = client.get("/api/admin/replies")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 2
    statuses = [item["status"] for item in body["data"]["items"]]
    assert "正常" in statuses
    assert "已删除" in statuses


def test_admin_list_replies_pagination():
    """管理员回复列表支持分页。"""
    client, admin = login_as_admin()
    club = create_test_club()
    author = create_student(username="pag_replies_author")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)

    for i in range(5):
        create_reply(post, author, content=f"回复{i}")

    resp = client.get("/api/admin/replies?page=1&page_size=2")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    assert body["data"]["total"] == 5
    assert len(body["data"]["items"]) == 2


def test_admin_list_replies_non_admin_rejected():
    """非管理员不能查看管理员回复列表。"""
    client, student = login_as_student("non_admin_replies")

    resp = client.get("/api/admin/replies")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "FORBIDDEN"


def test_admin_list_replies_empty():
    """无回复时返回空列表。"""
    client, admin = login_as_admin()

    resp = client.get("/api/admin/replies")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_admin_list_replies_unauthenticated_rejected():
    """未登录不能查看管理员回复列表。"""
    client = Client()

    resp = client.get("/api/admin/replies")

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"
