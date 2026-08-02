"""S19 三类数据概览 —— 后端测试。"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

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


def login_as_admin(username="admin_test"):
    admin = create_admin(username=username)
    client = Client()
    resp = login(client, admin.username, "AdminPass!2026")
    assert resp.status_code == 200
    return client, admin


def create_test_club(name="测试社团", category="学术科技", introduction="简介", logo="logos/test.png"):
    from clubs.models import Club
    return Club.objects.create(
        name=name, category=category, introduction=introduction, logo=logo,
    )


def create_test_membership(user, club, member_status="active", club_role="leader"):
    from clubs.models import ClubMembership
    return ClubMembership.objects.create(
        user=user, club=club, member_status=member_status, club_role=club_role,
    )


def create_test_recruitment(club, publisher, title="招新测试", **overrides):
    from clubs.models import Recruitment
    from datetime import timedelta
    now = timezone.now()
    data = {
        "title": title,
        "introduction": "招新简介",
        "requirements": "招新要求",
        "capacity": 10,
        "start_time": now - timedelta(days=1),
        "end_time": now + timedelta(days=7),
        "club": club,
        "publisher": publisher,
        **overrides,
    }
    return Recruitment.objects.create(**data)


def create_test_post(club, author, title="测试帖子", content="测试正文", status="正常"):
    from clubs.models import Post
    return Post.objects.create(
        title=title, content=content, club=club, author=author, status=status,
    )


def create_test_feedback(submitter, club, content="测试反馈", status="待处理"):
    from clubs.models import Feedback
    return Feedback.objects.create(
        submitter=submitter, club=club, content=content, status=status,
    )


def create_test_join_application(applicant, club, recruitment, status="待审核"):
    from clubs.models import JoinApplication
    return JoinApplication.objects.create(
        applicant=applicant,
        applicant_name_snapshot=applicant.name,
        applicant_major_class_snapshot=applicant.major_class,
        club=club,
        recruitment=recruitment,
        reason="测试申请理由",
        status=status,
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/admin/overview —— 管理员概览
# ═══════════════════════════════════════════════════════════════


class TestAdminOverview:
    """管理员概览测试。"""

    def test_admin_overview_success(self):
        """管理员查看概览返回正确计数。"""
        #创建 3 个学生和 2 个正常社团 + 1 个已注销社团
        create_student(username="s1")
        create_student(username="s2")
        create_student(username="s3")
        create_admin(username="another_admin")  #不算入 user_count
        create_test_club(name="社团A")
        create_test_club(name="社团B")
        cancelled = create_test_club(name="已注销社团")
        cancelled.status = "cancelled"
        cancelled.save()

        client, _admin = login_as_admin()

        resp = client.get("/api/admin/overview")
        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["user_count"] == 3
        assert body["data"]["normal_club_count"] == 2

    def test_admin_overview_zero(self):
        """无学生无社团时返回 0。"""
        client, _admin = login_as_admin()

        resp = client.get("/api/admin/overview")
        assert resp.status_code == 200
        body = response_body(resp)
        assert body["data"]["user_count"] == 0
        assert body["data"]["normal_club_count"] == 0

    def test_admin_overview_unauthenticated(self):
        """未登录返回 401。"""
        client = Client()
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 401

    def test_admin_overview_not_admin(self):
        """学生不能访问管理员概览。"""
        client, _student = login_as_student("normal_student")
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# GET /api/leader/clubs/{club_id}/overview —— 负责人概览
# ═══════════════════════════════════════════════════════════════


class TestLeaderOverview:
    """负责人概览测试。"""

    def test_leader_overview_success(self):
        """负责人查看概览返回 6 项正确统计。"""
        client, leader = login_as_student("club_leader")
        club = create_test_club()
        create_test_membership(leader, club, club_role="leader")

        #创建 3 个在社成员（含负责人本人）
        m1 = create_student(username="member1")
        m2 = create_student(username="member2")
        create_test_membership(m1, club, club_role="member")
        create_test_membership(m2, club, club_role="member")

        #创建 2 个待审核申请
        recruitment = create_test_recruitment(club, leader)
        a1 = create_student(username="applicant1")
        a2 = create_student(username="applicant2")
        create_test_join_application(a1, club, recruitment)
        create_test_join_application(a2, club, recruitment)

        #创建 1 个当前招新 + 1 个已提前结束招新
        create_test_recruitment(club, leader, title="当前招新1")
        from datetime import timedelta
        create_test_recruitment(
            club, leader, title="已结束招新",
            ended_early=True,
        )

        #创建 3 个正常帖子 + 1 个已删除帖子
        create_test_post(club, leader, title="帖子1")
        create_test_post(club, leader, title="帖子2")
        create_test_post(club, leader, title="帖子3")
        create_test_post(club, leader, title="已删除帖子", status="已删除")

        #创建 2 个待处理反馈 + 1 个已处理反馈
        create_test_feedback(m1, club, "反馈1")
        create_test_feedback(m2, club, "反馈2")
        create_test_feedback(m1, club, "已处理反馈", status="已处理")

        #创建 1 个待处理举报（通过帖子关联）
        from clubs.models import ContentReport
        post = create_test_post(club, leader, title="被举报帖子")
        ContentReport.objects.create(
            reporter=m1,
            reason="测试举报",
            post=post,
            status="待处理",
        )

        resp = client.get(f"/api/leader/clubs/{club.id}/overview")
        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        data = body["data"]
        #第一个 create_test_recruitment 也在未来，共 2 个当前招新
        assert data["active_member_count"] == 3
        assert data["pending_application_count"] == 2
        assert data["current_recruitment_count"] == 2
        assert data["post_count"] == 4  #帖子1/2/3 + 被举报帖子
        assert data["pending_feedback_count"] == 2
        assert data["pending_report_count"] == 1

    def test_leader_overview_minimal(self):
        """新社团只有负责人本人时各项统计正确。"""
        client, leader = login_as_student("new_leader")
        club = create_test_club()
        create_test_membership(leader, club, club_role="leader")

        resp = client.get(f"/api/leader/clubs/{club.id}/overview")
        assert resp.status_code == 200
        data = response_body(resp)["data"]
        #只有负责人本人一个在社成员
        assert data["active_member_count"] == 1
        assert data["pending_application_count"] == 0
        assert data["current_recruitment_count"] == 0
        assert data["post_count"] == 0
        assert data["pending_feedback_count"] == 0
        assert data["pending_report_count"] == 0

    def test_leader_overview_not_leader(self):
        """非负责人访问概览返回错误。"""
        client, student = login_as_student("not_leader")
        club = create_test_club()

        resp = client.get(f"/api/leader/clubs/{club.id}/overview")
        assert resp.status_code == 403

    def test_leader_overview_unauthenticated(self):
        """未登录访问概览返回 401。"""
        club = create_test_club()
        client = Client()
        resp = client.get(f"/api/leader/clubs/{club.id}/overview")
        assert resp.status_code == 401

    def test_leader_overview_cancelled_club(self):
        """已注销社团拒绝概览访问。"""
        client, leader = login_as_student("canc_leader")
        club = create_test_club()
        create_test_membership(leader, club, club_role="leader")
        club.status = "cancelled"
        club.save()

        resp = client.get(f"/api/leader/clubs/{club.id}/overview")
        #require_leader_of_club 返回 CLUB_CANCELLED（409）
        assert resp.status_code == 409
        assert response_body(resp)["code"] == "CLUB_CANCELLED"

    def test_leader_overview_pending_report_via_reply(self):
        """通过回复关联的举报也被正确统计。"""
        client, leader = login_as_student("rep_leader")
        club = create_test_club()
        create_test_membership(leader, club, club_role="leader")
        reporter = create_student(username="reporter")
        create_test_membership(reporter, club, club_role="member")

        post = create_test_post(club, reporter, title="有回复的帖子")
        from clubs.models import Reply, ContentReport
        reply = Reply.objects.create(content="测试回复", post=post, author=reporter)
        ContentReport.objects.create(
            reporter=leader,
            reason="举报回复",
            reply=reply,
            status="待处理",
        )

        resp = client.get(f"/api/leader/clubs/{club.id}/overview")
        assert resp.status_code == 200
        assert response_body(resp)["data"]["pending_report_count"] == 1


# ═══════════════════════════════════════════════════════════════
# GET /api/me/overview —— 学生概览
# ═══════════════════════════════════════════════════════════════


class TestStudentOverview:
    """学生概览测试。"""

    def test_student_overview_success(self):
        """学生查看概览返回正确计数和申请列表。"""
        client, student = login_as_student("overview_student")

        #加入 2 个正常社团
        club1 = create_test_club(name="社团1")
        club2 = create_test_club(name="社团2")
        leader = create_student(username="leader_user")
        create_test_membership(leader, club1, club_role="leader")
        create_test_membership(student, club1, club_role="member")
        create_test_membership(leader, club2, club_role="leader")
        create_test_membership(student, club2, club_role="member")

        #申请 1 个社团（待审核）
        recruitment = create_test_recruitment(club1, leader)
        create_test_join_application(student, club1, recruitment)

        resp = client.get("/api/me/overview")
        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        data = body["data"]
        assert data["joined_normal_club_count"] == 2
        assert len(data["join_applications"]) == 1
        assert data["join_applications"][0]["status"] == "待审核"

    def test_student_overview_excludes_cancelled_club(self):
        """已注销社团不计入加入社团数。"""
        client, student = login_as_student("excl_student")
        club = create_test_club(name="已注销社团")
        club.status = "cancelled"
        club.save()
        create_test_membership(student, club, club_role="member")

        resp = client.get("/api/me/overview")
        assert response_body(resp)["data"]["joined_normal_club_count"] == 0

    def test_student_overview_excludes_exited_membership(self):
        """已退出社团不计入加入社团数。"""
        client, student = login_as_student("exited_student")
        club = create_test_club()
        leader = create_student(username="exited_leader")
        create_test_membership(leader, club, club_role="leader")
        create_test_membership(student, club, member_status="exited")

        resp = client.get("/api/me/overview")
        assert response_body(resp)["data"]["joined_normal_club_count"] == 0

    def test_student_overview_applications_ordered(self):
        """入社申请按时间倒序排列。"""
        client, student = login_as_student("order_student")
        club = create_test_club()
        leader = create_student(username="order_leader")
        create_test_membership(leader, club, club_role="leader")
        recruitment = create_test_recruitment(club, leader)

        import time
        create_test_join_application(student, club, recruitment, status="已通过")
        time.sleep(0.1)
        create_test_join_application(student, club, recruitment, status="已拒绝")

        resp = client.get("/api/me/overview")
        apps = response_body(resp)["data"]["join_applications"]
        assert len(apps) == 2
        #较新的（已拒绝）在前
        assert apps[0]["status"] == "已拒绝"
        assert apps[1]["status"] == "已通过"

    def test_student_overview_empty(self):
        """未加入社团且无申请时返回 0 和空列表。"""
        client, _student = login_as_student("empty_student")

        resp = client.get("/api/me/overview")
        data = response_body(resp)["data"]
        assert data["joined_normal_club_count"] == 0
        assert data["join_applications"] == []

    def test_student_overview_unauthenticated(self):
        """未登录返回 401。"""
        client = Client()
        resp = client.get("/api/me/overview")
        assert resp.status_code == 401

    def test_student_overview_admin_rejected(self):
        """管理员不能访问学生概览。"""
        client, _admin = login_as_admin()
        resp = client.get("/api/me/overview")
        assert resp.status_code == 403

    def test_student_overview_disabled(self):
        """已停用学生已有会话访问概览返回 ACCOUNT_DISABLED。"""
        student = create_student(username="disabled_student")
        client = Client()
        resp = login(client, "disabled_student", "StrongPass!2026")
        assert resp.status_code == 200

        #停用该账号
        student.account_status = get_user_model().AccountStatus.DISABLED
        student.save()

        #已有会话访问受保护接口应被拒绝
        resp = client.get("/api/me/overview")
        assert resp.status_code == 403
        assert response_body(resp)["code"] == "ACCOUNT_DISABLED"
