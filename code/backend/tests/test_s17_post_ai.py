"""S17 帖子 AI — 后端测试。"""

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

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
        name=name, category=category, introduction=introduction, logo=logo,
    )


def create_test_membership(user, club, member_status="active", club_role="member"):
    from clubs.models import ClubMembership
    return ClubMembership.objects.create(
        user=user, club=club, member_status=member_status, club_role=club_role,
    )


def create_post(club, author, title="测试帖子", content="帖子内容", is_pinned=False):
    from clubs.models import Post
    return Post.objects.create(
        title=title, content=content, club=club, author=author, is_pinned=is_pinned,
    )


def create_reply(post, author, content="回复内容"):
    from clubs.models import Reply
    return Reply.objects.create(content=content, post=post, author=author)


#Mock DeepSeek 调用回答
MOCK_AI_ANSWER = "这是AI生成的测试回答。"


def mock_deepseek_success(system_prompt, user_prompt):
    return MOCK_AI_ANSWER


# ═══════════════════════════════════════════════════════════════
# POST /api/posts/{post_id}/ai — 帖子 AI
# ═══════════════════════════════════════════════════════════════


class TestPostAiSuccess:
    """正常路径测试。"""

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_summarize_success(self, _mock):
        """总结操作成功返回 AI 回答。"""
        client, user = login_as_student("summarize_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user, title="AI社团活动", content="本周举办了精彩的活动。")

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["answer"] == MOCK_AI_ANSWER
        assert body["data"]["truncated"] is False
        assert "warning" not in body["data"]

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_extract_viewpoints_success(self, _mock):
        """提取主要观点操作成功。"""
        client, user = login_as_student("viewpoint_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user, title="多观点帖子", content="观点A，观点B，观点C。")

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "提取主要观点"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["answer"] == MOCK_AI_ANSWER

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_qa_success(self, _mock):
        """问答操作成功返回 AI 回答。"""
        client, user = login_as_student("qa_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user, title="活动安排", content="活动将在周五下午3点举行。")

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "问答", "question": "活动什么时候举行？"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["answer"] == MOCK_AI_ANSWER

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_summarize_with_replies(self, _mock):
        """包含回复的总结操作成功。"""
        client, user = login_as_student("replies_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)
        #另一成员创建回复
        other = create_student(username="other_member")
        create_test_membership(other, club)
        create_reply(post, other, "回复1")
        create_reply(post, other, "回复2")

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    @override_settings(AI_MAX_CONTENT_CHARS=50)
    def test_content_truncation_warning(self, _mock):
        """超长内容截断后返回 warning。"""
        client, user = login_as_student("trunc_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user, title="长标题帖子讨论了很多内容", content="这是一段非常长的帖子内容，包含很多文字和详细的信息需要被截断处理。")

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["truncated"] is True
        assert "warning" in body["data"]
        assert "内容较长" in body["data"]["warning"]


class TestPostAiValidation:
    """输入校验测试。"""

    def test_invalid_operation(self):
        """无效操作返回 INVALID_AI_OPERATION。"""
        client, user = login_as_student("bad_op_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "无效操作"}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "INVALID_AI_OPERATION"

    def test_qa_without_question(self):
        """问答操作缺少问题返回 QUESTION_REQUIRED。"""
        client, user = login_as_student("no_q_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "问答"}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "QUESTION_REQUIRED"

    def test_qa_with_empty_question(self):
        """问答操作空问题返回 QUESTION_REQUIRED。"""
        client, user = login_as_student("empty_q_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "问答", "question": "   "}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "QUESTION_REQUIRED"

    def test_summarize_with_extra_question_rejected(self):
        """总结操作携带额外问题被拒绝。"""
        client, user = login_as_student("extra_input_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结", "question": "还有别的问题吗？"}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "VALIDATION_ERROR"

    def test_extract_viewpoints_with_extra_question_rejected(self):
        """提取主要观点操作携带额外问题被拒绝。"""
        client, user = login_as_student("extra_vp_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "提取主要观点", "question": "问题？"}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "VALIDATION_ERROR"

    def test_missing_operation(self):
        """缺少 operation 字段返回 INVALID_AI_OPERATION。"""
        client, user = login_as_student("no_op_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "INVALID_AI_OPERATION"

    def test_get_method_not_allowed(self):
        """GET 请求返回 405。"""
        client, user = login_as_student("get_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.get(f"/api/posts/{post.id}/ai")

        assert resp.status_code == 405


class TestPostAiPermission:
    """权限校验测试。"""

    def test_post_not_found(self):
        """帖子不存在返回 RESOURCE_NOT_FOUND。"""
        client, user = login_as_student("nf_user")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            "/api/posts/99999/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 404
        body = response_body(resp)
        assert body["code"] == "RESOURCE_NOT_FOUND"

    def test_deleted_post_rejected(self):
        """已删除帖子返回 POST_DELETED。"""
        from clubs.models import Post

        client, user = login_as_student("del_post_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)
        post.status = Post.Status.DELETED
        post.save()

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 409
        body = response_body(resp)
        assert body["code"] == "POST_DELETED"

    def test_not_club_member_rejected(self):
        """非社团成员返回 NOT_CLUB_MEMBER。"""
        client, user = login_as_student("non_member")
        club = create_test_club()
        #不创建成员关系
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "NOT_CLUB_MEMBER"

    def test_exited_member_rejected(self):
        """已退出成员返回 MEMBERSHIP_INACTIVE。"""
        client, user = login_as_student("exited_member")
        club = create_test_club()
        create_test_membership(user, club, member_status="exited")
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "MEMBERSHIP_INACTIVE"

    def test_cancelled_club_rejected(self):
        """已注销社团返回 CLUB_CANCELLED。"""
        from clubs.models import Club

        client, user = login_as_student("cancelled_club_user")
        club = create_test_club()
        club.status = Club.Status.CANCELLED
        club.save()
        create_test_membership(user, club)
        post = create_post(club, user)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 409
        body = response_body(resp)
        assert body["code"] == "CLUB_CANCELLED"

    def test_unauthenticated_rejected(self):
        """未登录返回 UNAUTHENTICATED。"""
        club = create_test_club()
        user = create_student(username="anon_post_author")
        create_test_membership(user, club)
        post = create_post(club, user)

        client = Client()
        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 401
        body = response_body(resp)
        assert body["code"] == "UNAUTHENTICATED"

    def test_disabled_account_rejected(self):
        """停用账号返回 ACCOUNT_DISABLED。"""
        client, user = login_as_student("disabled_ai_user")
        club = create_test_club()
        create_test_membership(user, club)
        post = create_post(club, user)

        #停用账号
        user.account_status = get_user_model().AccountStatus.DISABLED
        user.save()

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "ACCOUNT_DISABLED"

    def test_admin_cannot_use_ai(self):
        """管理员不能使用帖子 AI（仅学生可用）。"""
        admin = create_admin()
        client = Client()
        resp = login(client, admin.username, "AdminPass!2026")
        assert resp.status_code == 200

        club = create_test_club()
        student = create_student(username="post_owner")
        create_test_membership(student, club)
        post = create_post(club, student)

        resp = client.post(
            f"/api/posts/{post.id}/ai",
            data=json.dumps({"operation": "总结"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "FORBIDDEN"
