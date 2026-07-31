"""S11 帖子回复与作者通知 — 后端测试。"""

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


def login(client, username, password):
    return client.post(
        LOGIN_URL,
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


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
# GET /api/posts/{post_id}/replies — 查看回复列表
# ═══════════════════════════════════════════════════════════════


def test_list_replies_success():
    """在社成员成功查看正常回复列表，按 ID 正序排列。"""
    client, student = login_as_student()
    member2 = create_student(username="member_r1")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(member2, club, member_status="active", club_role="member")
    post = create_post(club, student, title="目标帖子")

    r1 = create_reply(post, member2, content="第一个回复")
    r2 = create_reply(post, student, content="第二个回复")

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 2
    items = body["data"]["items"]
    assert len(items) == 2
    assert items[0]["id"] == r1.id
    assert items[0]["content"] == "第一个回复"
    assert items[1]["id"] == r2.id
    assert items[1]["content"] == "第二个回复"


def test_list_replies_author_info():
    """回复列表包含正确的作者信息。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)
    create_reply(post, student, content="我的回复")

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 200
    body = response_body(resp)
    item = body["data"]["items"][0]
    assert item["author"]["id"] == student.id
    assert item["author"]["username"] == student.username


def test_list_replies_excludes_deleted():
    """回复列表不包含已删除回复。"""
    client, student = login_as_student()
    member2 = create_student(username="member_r2")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(member2, club, member_status="active", club_role="member")
    post = create_post(club, student)
    from clubs.models import Reply

    create_reply(post, member2, content="正常回复")
    r2 = create_reply(post, student, content="已删除回复")
    r2.status = Reply.Status.DELETED
    r2.save()

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["content"] == "正常回复"


def test_list_replies_empty():
    """无回复时返回空列表。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_list_replies_deleted_post_rejected():
    """已删除帖子的回复不可见。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)
    from clubs.models import Post

    post.status = Post.Status.DELETED
    post.save()

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "RESOURCE_DELETED"


def test_list_replies_non_member_rejected():
    """非社团成员不能查看回复。"""
    client, student = login_as_student()
    club = create_test_club()
    author = create_student(username="author_r3")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_MEMBER"


def test_list_replies_ex_member_rejected():
    """已退出成员不能查看回复。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="exited", club_role="member")
    post = create_post(club, student)

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_list_replies_nonexistent_post():
    """查看不存在帖子的回复返回 404。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.get("/api/posts/99999/replies")

    assert resp.status_code == 404
    body = response_body(resp)
    assert body["code"] == "RESOURCE_NOT_FOUND"


def test_list_replies_unauthenticated_rejected():
    """未登录不能查看回复。"""
    club = create_test_club()
    author = create_student(username="author_r4")
    post = create_post(club, author)
    client = Client()

    resp = client.get(f"/api/posts/{post.id}/replies")

    assert resp.status_code == 401


def test_list_replies_pagination():
    """回复列表支持分页。"""
    client, student = login_as_student()
    member2 = create_student(username="member_r5")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(member2, club, member_status="active", club_role="member")
    post = create_post(club, student)

    for i in range(5):
        create_reply(post, member2, content=f"回复{i}")

    resp = client.get(f"/api/posts/{post.id}/replies?page=1&page_size=2")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    assert body["data"]["total"] == 5
    assert len(body["data"]["items"]) == 2


# ═══════════════════════════════════════════════════════════════
# POST /api/posts/{post_id}/replies — 发布回复
# ═══════════════════════════════════════════════════════════════


def test_create_reply_success():
    """在社成员成功回复帖子。"""
    client, student = login_as_student("replier_01")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "这是一条回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["content"] == "这是一条回复"
    assert body["data"]["post_id"] == post.id
    assert body["data"]["author"]["id"] == student.id
    assert body["data"]["status"] == "正常"


def test_create_reply_leader_can_reply():
    """负责人也可以回复帖子。"""
    client, leader = login_as_student("leader_replier")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    post = create_post(club, leader)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "负责人回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["data"]["content"] == "负责人回复"


def test_create_reply_notification_to_author():
    """回复帖子时，帖子作者收到通知（作者不给自己发通知）。"""
    #作者创建帖子，另一个成员回复
    author_client, author = login_as_student("post_author")
    replier_client, replier = login_as_student("post_replier")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    create_test_membership(replier, club, member_status="active", club_role="member")
    post = create_post(club, author, title="通知测试帖子")

    resp = replier_client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "触发通知的回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 201

    #验证通知已生成
    from clubs.models import Notification

    notification = Notification.objects.filter(
        recipient=author,
        type=Notification.Type.REPLY,
    ).first()

    assert notification is not None
    assert "帖子「通知测试帖子」" in notification.content


def test_create_reply_self_reply_no_notification():
    """作者回复自己的帖子不产生通知。"""
    client, author = login_as_student("self_replier")
    club = create_test_club()
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author, title="自己的帖子")

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "自己回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 201

    #验证没有通知
    from clubs.models import Notification

    count = Notification.objects.filter(
        recipient=author,
        type=Notification.Type.REPLY,
    ).count()

    assert count == 0


def test_create_reply_empty_content_rejected():
    """内容为空拒绝。"""
    client, student = login_as_student("replier_02")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_create_reply_content_too_long():
    """回复超过 1000 字拒绝。"""
    client, student = login_as_student("replier_03")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "R" * 1001}),
        content_type="application/json",
    )

    assert resp.status_code == 422
    body = response_body(resp)
    assert body["code"] == "VALIDATION_ERROR"


def test_create_reply_deleted_post_rejected():
    """已删除帖子不能回复。"""
    client, replier = login_as_student("replier_04")
    club = create_test_club()
    create_test_membership(replier, club, member_status="active", club_role="member")
    post = create_post(club, replier)
    from clubs.models import Post

    post.status = Post.Status.DELETED
    post.save()

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "回复已删除帖子"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "POST_DELETED"


def test_create_reply_nonexistent_post():
    """回复不存在的帖子返回 404。"""
    client, student = login_as_student("replier_05")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        "/api/posts/99999/replies",
        data=json.dumps({"content": "回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 404


def test_create_reply_non_member_rejected():
    """非社团成员不能回复。"""
    client, student = login_as_student("replier_06")
    club = create_test_club()
    author = create_student(username="author_r6")
    create_test_membership(author, club, member_status="active", club_role="member")
    post = create_post(club, author)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_MEMBER"


def test_create_reply_ex_member_rejected():
    """已退出成员不能回复。"""
    client, student = login_as_student("replier_07")
    club = create_test_club()
    create_test_membership(student, club, member_status="exited", club_role="member")
    post = create_post(club, student)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_create_reply_unauthenticated_rejected():
    """未登录不能回复。"""
    club = create_test_club()
    author = create_student(username="author_r8")
    post = create_post(club, author)
    client = Client()

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "回复"}),
        content_type="application/json",
    )

    assert resp.status_code == 401


def test_create_reply_rejects_extra_fields():
    """回复时拒绝 content 之外的字段。"""
    client, student = login_as_student("replier_09")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)

    resp = client.post(
        f"/api/posts/{post.id}/replies",
        data=json.dumps({"content": "回复", "status": "已删除"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"
