"""S09 社团公告 — 后端测试。"""

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


def create_announcement(club, publisher, title="测试公告", content="公告内容", is_pinned=False):
    from clubs.models import Announcement

    return Announcement.objects.create(
        title=title,
        content=content,
        club=club,
        publisher=publisher,
        is_pinned=is_pinned,
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/clubs/{club_id}/announcements — 成员查看公告
# ═══════════════════════════════════════════════════════════════


def test_member_list_announcements_success():
    """在社成员成功查看正常公告，置顶优先。"""
    client, student = login_as_student()
    leader = create_student(username="leader_01")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(leader, club, member_status="active", club_role="leader")

    #创建公告（先普通，后置顶）
    a1 = create_announcement(club, leader, title="普通公告", is_pinned=False)
    a2 = create_announcement(club, leader, title="置顶公告", is_pinned=True)

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 2
    items = body["data"]["items"]
    #置顶公告应在前面
    assert items[0]["id"] == a2.id
    assert items[0]["is_pinned"] is True
    assert items[1]["id"] == a1.id


def test_member_list_announcements_excludes_deleted():
    """成员查看不包括已删除公告。"""
    client, student = login_as_student()
    leader = create_student(username="leader_02")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(leader, club, member_status="active", club_role="leader")

    create_announcement(club, leader, title="正常公告")
    from clubs.models import Announcement

    create_announcement(club, leader, title="已删除公告")
    #手动设置第二个为已删除
    Announcement.objects.filter(title="已删除公告").update(status=Announcement.Status.DELETED)

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["title"] == "正常公告"


def test_member_list_announcements_empty():
    """无公告时返回空列表。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_member_list_announcements_non_member_rejected():
    """非社团成员不能查看公告。"""
    client, student = login_as_student()
    club = create_test_club()
    #student 不是该社团成员

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_MEMBER"


def test_member_list_announcements_ex_member_rejected():
    """已退出成员不能查看公告。"""
    client, student = login_as_student()
    club = create_test_club()
    create_test_membership(student, club, member_status="exited", club_role="member")

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "MEMBERSHIP_INACTIVE"


def test_member_list_announcements_cancelled_club_rejected():
    """已注销社团成员不能查看公告。"""
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

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "CLUB_CANCELLED"


def test_member_list_announcements_unauthenticated_rejected():
    """未登录不能查看公告。"""
    club = create_test_club()
    client = Client()

    resp = client.get(f"/api/clubs/{club.id}/announcements")

    assert resp.status_code == 401
    body = response_body(resp)
    assert body["code"] == "UNAUTHENTICATED"


# ═══════════════════════════════════════════════════════════════
# POST /api/leader/clubs/{club_id}/announcements — 负责人发布公告
# ═══════════════════════════════════════════════════════════════


def test_leader_create_announcement_success():
    """负责人成功发布公告。"""
    client, leader = login_as_student("leader_10")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/leader/clubs/{club.id}/announcements",
        data=json.dumps({
            "title": "新公告标题",
            "content": "公告正文内容",
        }),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["title"] == "新公告标题"
    assert body["data"]["content"] == "公告正文内容"
    assert body["data"]["is_pinned"] is False
    assert body["data"]["status"] == "正常"
    assert body["data"]["publisher"]["id"] == leader.id


def test_leader_create_announcement_pinned():
    """负责人发布置顶公告。"""
    client, leader = login_as_student("leader_11")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/leader/clubs/{club.id}/announcements",
        data=json.dumps({
            "title": "置顶公告",
            "content": "重要内容",
            "is_pinned": True,
        }),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["data"]["is_pinned"] is True


def test_leader_create_announcement_empty_title_rejected():
    """标题为空拒绝。"""
    client, leader = login_as_student("leader_12")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/leader/clubs/{club.id}/announcements",
        data=json.dumps({"title": "", "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_leader_create_announcement_empty_content_rejected():
    """内容为空拒绝。"""
    client, leader = login_as_student("leader_13")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.post(
        f"/api/leader/clubs/{club.id}/announcements",
        data=json.dumps({"title": "标题", "content": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    body = response_body(resp)
    assert body["code"] == "INVALID_REQUEST"


def test_leader_create_announcement_non_leader_rejected():
    """普通成员不能发布公告。"""
    client, student = login_as_student("member_14")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")

    resp = client.post(
        f"/api/leader/clubs/{club.id}/announcements",
        data=json.dumps({"title": "标题", "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_create_announcement_unauthenticated_rejected():
    """未登录不能发布公告。"""
    club = create_test_club()
    client = Client()

    resp = client.post(
        f"/api/leader/clubs/{club.id}/announcements",
        data=json.dumps({"title": "标题", "content": "内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# PATCH /api/leader/announcements/{id} — 负责人修改公告
# ═══════════════════════════════════════════════════════════════


def test_leader_update_announcement_success():
    """负责人成功修改公告标题和内容。"""
    client, leader = login_as_student("leader_20")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    announcement = create_announcement(club, leader, title="原标题", content="原内容")

    resp = client.patch(
        f"/api/leader/announcements/{announcement.id}",
        data=json.dumps({"title": "新标题", "content": "新内容"}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["title"] == "新标题"
    assert body["data"]["content"] == "新内容"


def test_leader_update_announcement_pin():
    """负责人置顶/取消置顶公告。"""
    client, leader = login_as_student("leader_21")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    announcement = create_announcement(club, leader, is_pinned=False)

    #置顶
    resp = client.patch(
        f"/api/leader/announcements/{announcement.id}",
        data=json.dumps({"is_pinned": True}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["is_pinned"] is True

    #取消置顶
    resp2 = client.patch(
        f"/api/leader/announcements/{announcement.id}",
        data=json.dumps({"is_pinned": False}),
        content_type="application/json",
    )

    assert resp2.status_code == 200
    body2 = response_body(resp2)
    assert body2["data"]["is_pinned"] is False


def test_leader_update_deleted_announcement_rejected():
    """已删除公告不能修改。"""
    client, leader = login_as_student("leader_22")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    announcement = create_announcement(club, leader)
    from clubs.models import Announcement

    announcement.status = Announcement.Status.DELETED
    announcement.save()

    resp = client.patch(
        f"/api/leader/announcements/{announcement.id}",
        data=json.dumps({"title": "新标题"}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "ANNOUNCEMENT_DELETED"


def test_leader_update_announcement_other_club_rejected():
    """不能修改其他社团的公告。"""
    client, leader = login_as_student("leader_23")
    club_a = create_test_club(name="社团A")
    club_b = create_test_club(name="社团B")
    create_test_membership(leader, club_a, member_status="active", club_role="leader")
    other_leader = create_student(username="other_leader")
    create_test_membership(other_leader, club_b, member_status="active", club_role="leader")
    announcement = create_announcement(club_b, other_leader)

    resp = client.patch(
        f"/api/leader/announcements/{announcement.id}",
        data=json.dumps({"title": "新标题"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_update_announcement_nonexistent():
    """修改不存在的公告返回 404。"""
    client, leader = login_as_student("leader_24")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.patch(
        "/api/leader/announcements/99999",
        data=json.dumps({"title": "新标题"}),
        content_type="application/json",
    )

    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# DELETE /api/leader/announcements/{id} — 负责人逻辑删除公告
# ═══════════════════════════════════════════════════════════════


def test_leader_delete_announcement_success():
    """负责人成功逻辑删除公告。"""
    client, leader = login_as_student("leader_30")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    announcement = create_announcement(club, leader)

    resp = client.delete(
        f"/api/leader/announcements/{announcement.id}",
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["status"] == "已删除"

    #成员不再看到该公告
    member_client, member = login_as_student("member_31")
    create_test_membership(member, club, member_status="active", club_role="member")
    resp2 = member_client.get(f"/api/clubs/{club.id}/announcements")
    body2 = response_body(resp2)
    assert body2["data"]["total"] == 0


def test_leader_delete_already_deleted_rejected():
    """已删除公告不能重复删除。"""
    client, leader = login_as_student("leader_32")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    announcement = create_announcement(club, leader)
    from clubs.models import Announcement

    announcement.status = Announcement.Status.DELETED
    announcement.save()

    resp = client.delete(
        f"/api/leader/announcements/{announcement.id}",
        content_type="application/json",
    )

    assert resp.status_code == 409
    body = response_body(resp)
    assert body["code"] == "ANNOUNCEMENT_DELETED"


def test_leader_delete_announcement_non_leader_rejected():
    """非负责人不能删除公告。"""
    client, student = login_as_student("member_33")
    leader = create_student(username="leader_33")
    club = create_test_club()
    create_test_membership(student, club, member_status="active", club_role="member")
    create_test_membership(leader, club, member_status="active", club_role="leader")
    announcement = create_announcement(club, leader)

    resp = client.delete(
        f"/api/leader/announcements/{announcement.id}",
        content_type="application/json",
    )

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "NOT_CLUB_LEADER"


def test_leader_delete_announcement_nonexistent():
    """删除不存在的公告返回 404。"""
    client, leader = login_as_student("leader_34")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")

    resp = client.delete(
        "/api/leader/announcements/99999",
        content_type="application/json",
    )

    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# GET /api/admin/clubs/{club_id}/announcements — 管理员查看历史
# ═══════════════════════════════════════════════════════════════


def test_admin_list_announcements_cancelled_club_success():
    """管理员可以查看已注销社团的全部公告。"""
    admin_client, admin = login_as_admin()
    from clubs.models import Club, Announcement

    leader = create_student(username="leader_40")
    club = Club.objects.create(
        name="已注销社团",
        category="学术科技",
        introduction="简介",
        logo="logos/test.png",
        status=Club.Status.CANCELLED,
    )

    a1 = create_announcement(club, leader, title="正常公告")
    a2 = create_announcement(club, leader, title="已删除公告")
    a2.status = Announcement.Status.DELETED
    a2.save()

    resp = admin_client.get(f"/api/admin/clubs/{club.id}/announcements")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 2


def test_admin_list_announcements_normal_club_rejected():
    """管理员不能查看正常社团的公告（应使用成员接口）。"""
    admin_client, admin = login_as_admin()
    leader = create_student(username="leader_41")
    club = create_test_club()
    create_announcement(club, leader)

    resp = admin_client.get(f"/api/admin/clubs/{club.id}/announcements")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "FORBIDDEN"


def test_admin_list_announcements_non_admin_rejected():
    """非管理员不能使用管理员公告接口。"""
    client, student = login_as_student("student_42")
    from clubs.models import Club

    club = Club.objects.create(
        name="已注销社团2",
        category="学术科技",
        introduction="简介",
        logo="logos/test.png",
        status=Club.Status.CANCELLED,
    )

    resp = client.get(f"/api/admin/clubs/{club.id}/announcements")

    assert resp.status_code == 403
    body = response_body(resp)
    assert body["code"] == "FORBIDDEN"


# ═══════════════════════════════════════════════════════════════
# GET /api/leader/clubs/{club_id}/announcements — 负责人查看全量
# ═══════════════════════════════════════════════════════════════


def test_leader_list_announcements_includes_deleted():
    """负责人查看包括已删除公告。"""
    client, leader = login_as_student("leader_50")
    club = create_test_club()
    create_test_membership(leader, club, member_status="active", club_role="leader")
    from clubs.models import Announcement

    a1 = create_announcement(club, leader, title="正常公告")
    a2 = create_announcement(club, leader, title="已删除公告")
    a2.status = Announcement.Status.DELETED
    a2.save()

    resp = client.get(f"/api/leader/clubs/{club.id}/announcements")

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 2
