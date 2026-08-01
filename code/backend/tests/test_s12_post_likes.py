"""S12 帖子点赞 — 后端测试。"""

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


def setup_member_and_post():
    """创建学生、社团、成员关系和帖子的快捷函数。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    post = create_post(club, student)
    return client, student, club, post


# ═══════════════════════════════════════════════════════════════
# POST /api/posts/{post_id}/like — 点赞帖子
# ═══════════════════════════════════════════════════════════════


def test_like_post_success():
    """在社成员成功点赞正常帖子，返回 like_count=1 和 liked_by_me=true。"""
    client, student, _club, post = setup_member_and_post()

    resp = client.post(f"/api/posts/{post.id}/like")

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["id"] == post.id
    assert body["data"]["like_count"] == 1
    assert body["data"]["liked_by_me"] is True


def test_like_post_increments_count():
    """多个用户点赞，like_count 正确累加。"""
    client, student, club, post = setup_member_and_post()

    #第二个成员
    member2 = create_student(username="member_02")
    client2 = Client()
    resp = login(client2, "member_02", "StrongPass!2026")
    assert resp.status_code == 200
    create_test_membership(member2, club, member_status="active", club_role="member")

    #第三个成员
    member3 = create_student(username="member_03")
    client3 = Client()
    resp = login(client3, "member_03", "StrongPass!2026")
    assert resp.status_code == 200
    create_test_membership(member3, club, member_status="active", club_role="member")

    #学生1点赞
    resp1 = client.post(f"/api/posts/{post.id}/like")
    assert resp1.status_code == 201
    assert response_body(resp1)["data"]["like_count"] == 1

    #学生2点赞
    resp2 = client2.post(f"/api/posts/{post.id}/like")
    assert resp2.status_code == 201
    assert response_body(resp2)["data"]["like_count"] == 2

    #学生3点赞
    resp3 = client3.post(f"/api/posts/{post.id}/like")
    assert resp3.status_code == 201
    assert response_body(resp3)["data"]["like_count"] == 3


def test_like_post_own_liked_by_me():
    """点赞后 liked_by_me 为 true，未点赞用户看到 false。"""
    client, student, club, post = setup_member_and_post()

    member2 = create_student(username="member_02")
    client2 = Client()
    resp = login(client2, "member_02", "StrongPass!2026")
    assert resp.status_code == 200
    create_test_membership(member2, club, member_status="active", club_role="member")

    #学生1点赞
    client.post(f"/api/posts/{post.id}/like")

    #学生1看到 liked_by_me=true
    resp1 = client.get(f"/api/posts/{post.id}")
    assert response_body(resp1)["data"]["liked_by_me"] is True

    #学生2未点赞，看到 liked_by_me=false
    resp2 = client2.get(f"/api/posts/{post.id}")
    assert response_body(resp2)["data"]["liked_by_me"] is False


def test_like_post_duplicate():
    """重复点赞返回 DUPLICATE_LIKE。"""
    client, _student, _club, post = setup_member_and_post()

    #第一次点赞成功
    resp1 = client.post(f"/api/posts/{post.id}/like")
    assert resp1.status_code == 201

    #第二次点赞失败
    resp2 = client.post(f"/api/posts/{post.id}/like")
    assert resp2.status_code == 409
    body = response_body(resp2)
    assert body["code"] == "DUPLICATE_LIKE"


def test_like_post_deleted():
    """已删除帖子不能点赞，返回 POST_DELETED。"""
    client, student, club, post = setup_member_and_post()

    #软删除帖子
    from clubs.models import Post
    post.status = Post.Status.DELETED
    post.save()

    resp = client.post(f"/api/posts/{post.id}/like")
    assert resp.status_code == 409
    assert response_body(resp)["code"] == "POST_DELETED"


def test_like_post_non_member():
    """非社团成员不能点赞，返回 NOT_CLUB_MEMBER。"""
    client, student = login_as_student()
    club = create_test_club()
    #不创建成员关系
    post = create_post(club, student)

    resp = client.post(f"/api/posts/{post.id}/like")
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_MEMBER"


def test_like_post_ex_member():
    """已退出成员不能点赞，返回 MEMBERSHIP_INACTIVE。"""
    client, student, club, post = setup_member_and_post()

    #将成员状态改为已退出
    from clubs.models import ClubMembership
    membership = ClubMembership.objects.get(user=student, club=club)
    membership.member_status = ClubMembership.MemberStatus.EXITED
    membership.save()

    resp = client.post(f"/api/posts/{post.id}/like")
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "MEMBERSHIP_INACTIVE"


def test_like_post_cancelled_club():
    """已注销社团的帖子不能点赞，返回 CLUB_CANCELLED。"""
    client, student, club, post = setup_member_and_post()

    club.status = "已注销"
    club.save()

    resp = client.post(f"/api/posts/{post.id}/like")
    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_like_post_unauthenticated():
    """未登录不能点赞，返回 UNAUTHENTICATED。"""
    _client, _student, _club, post = setup_member_and_post()

    anon_client = Client()
    resp = anon_client.post(f"/api/posts/{post.id}/like")
    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_like_post_nonexistent():
    """不存在的帖子点赞返回 RESOURCE_NOT_FOUND。"""
    client, _student, _club, _post = setup_member_and_post()

    resp = client.post("/api/posts/99999/like")
    assert resp.status_code == 404
    assert response_body(resp)["code"] == "RESOURCE_NOT_FOUND"


def test_like_post_list_reflects_like():
    """帖子列表中的 like_count 和 liked_by_me 反映点赞状态。"""
    client, student, club, post = setup_member_and_post()

    #点赞前列表检查
    resp_before = client.get(f"/api/clubs/{club.id}/posts")
    items_before = response_body(resp_before)["data"]["items"]
    post_before = next(p for p in items_before if p["id"] == post.id)
    assert post_before["like_count"] == 0
    assert post_before["liked_by_me"] is False

    #点赞
    client.post(f"/api/posts/{post.id}/like")

    #点赞后列表检查
    resp_after = client.get(f"/api/clubs/{club.id}/posts")
    items_after = response_body(resp_after)["data"]["items"]
    post_after = next(p for p in items_after if p["id"] == post.id)
    assert post_after["like_count"] == 1
    assert post_after["liked_by_me"] is True


# ═══════════════════════════════════════════════════════════════
# DELETE /api/posts/{post_id}/like — 取消点赞
# ═══════════════════════════════════════════════════════════════


def test_unlike_post_success():
    """点赞后取消点赞，返回 like_count=0 和 liked_by_me=false。"""
    client, _student, _club, post = setup_member_and_post()

    #先点赞
    client.post(f"/api/posts/{post.id}/like")

    #取消点赞
    resp = client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["id"] == post.id
    assert body["data"]["like_count"] == 0
    assert body["data"]["liked_by_me"] is False


def test_unlike_post_decrements_count():
    """多个用户点赞后一人取消，like_count 正确减少。"""
    client, student, club, post = setup_member_and_post()

    member2 = create_student(username="member_02")
    client2 = Client()
    resp = login(client2, "member_02", "StrongPass!2026")
    assert resp.status_code == 200
    create_test_membership(member2, club, member_status="active", club_role="member")

    #两人都点赞
    client.post(f"/api/posts/{post.id}/like")
    client2.post(f"/api/posts/{post.id}/like")

    #学生1取消点赞
    resp_unlike = client.delete(f"/api/posts/{post.id}/like")
    assert resp_unlike.status_code == 200
    assert response_body(resp_unlike)["data"]["like_count"] == 1

    #学生2仍看到 liked_by_me=true
    resp2 = client2.get(f"/api/posts/{post.id}")
    assert response_body(resp2)["data"]["liked_by_me"] is True
    assert response_body(resp2)["data"]["like_count"] == 1


def test_unlike_not_exists():
    """取消不存在的点赞返回 LIKE_NOT_FOUND。"""
    client, _student, _club, post = setup_member_and_post()

    resp = client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 404
    assert response_body(resp)["code"] == "LIKE_NOT_FOUND"


def test_unlike_post_deleted():
    """已删除帖子不能取消点赞，返回 POST_DELETED。"""
    client, student, club, post = setup_member_and_post()

    #先点赞
    client.post(f"/api/posts/{post.id}/like")

    #软删除帖子
    from clubs.models import Post
    post.status = Post.Status.DELETED
    post.save()

    resp = client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 409
    assert response_body(resp)["code"] == "POST_DELETED"


def test_unlike_post_non_member():
    """非社团成员不能取消点赞。"""
    client, student = login_as_student()
    club = create_test_club()
    post = create_post(club, student)

    resp = client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_MEMBER"


def test_unlike_post_ex_member():
    """已退出成员不能取消点赞，返回 MEMBERSHIP_INACTIVE。"""
    client, student, club, post = setup_member_and_post()

    #先点赞
    client.post(f"/api/posts/{post.id}/like")

    #退出社团
    from clubs.models import ClubMembership
    membership = ClubMembership.objects.get(user=student, club=club)
    membership.member_status = ClubMembership.MemberStatus.EXITED
    membership.save()

    resp = client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "MEMBERSHIP_INACTIVE"


def test_unlike_post_cancelled_club():
    """已注销社团的帖子不能取消点赞，返回 CLUB_CANCELLED。"""
    client, student, club, post = setup_member_and_post()

    #先点赞
    client.post(f"/api/posts/{post.id}/like")

    club.status = "已注销"
    club.save()

    resp = client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_unlike_post_unauthenticated():
    """未登录不能取消点赞，返回 UNAUTHENTICATED。"""
    _client, _student, _club, post = setup_member_and_post()

    anon_client = Client()
    resp = anon_client.delete(f"/api/posts/{post.id}/like")
    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_can_like_again_after_unlike():
    """取消点赞后可以再次点赞。"""
    client, _student, _club, post = setup_member_and_post()

    #点赞 → 取消 → 再点赞
    resp1 = client.post(f"/api/posts/{post.id}/like")
    assert resp1.status_code == 201
    assert response_body(resp1)["data"]["like_count"] == 1

    resp2 = client.delete(f"/api/posts/{post.id}/like")
    assert resp2.status_code == 200
    assert response_body(resp2)["data"]["like_count"] == 0

    resp3 = client.post(f"/api/posts/{post.id}/like")
    assert resp3.status_code == 201
    assert response_body(resp3)["data"]["like_count"] == 1
    assert response_body(resp3)["data"]["liked_by_me"] is True


def test_wrong_method_on_like():
    """不支持的 HTTP 方法返回 405。"""
    client, _student, _club, post = setup_member_and_post()

    resp = client.put(f"/api/posts/{post.id}/like")
    assert resp.status_code == 405
    assert response_body(resp)["code"] == "INVALID_REQUEST"
