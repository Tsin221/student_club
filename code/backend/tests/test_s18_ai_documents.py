"""S18 AI 文档生成 — 后端测试。"""

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


#Mock DeepSeek 调用回答
MOCK_AI_DOC_DRAFT = "这是AI生成的测试文档草稿。"


def mock_deepseek_success(system_prompt, user_prompt):
    return MOCK_AI_DOC_DRAFT


# ═══════════════════════════════════════════════════════════════
# POST /api/leader/clubs/{club_id}/ai-documents — AI 文档生成
# ═══════════════════════════════════════════════════════════════


class TestAiDocumentSuccess:
    """正常路径测试。"""

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_generate_announcement_success(self, _mock):
        """生成社团公告草稿成功。"""
        client, user = login_as_student("ann_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({
                "document_type": "社团公告",
                "title_or_topic": "社团招新通知",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["draft"] == MOCK_AI_DOC_DRAFT

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_generate_recruitment_success(self, _mock):
        """生成招新文案草稿成功。"""
        client, user = login_as_student("rec_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "招新文案"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["draft"] == MOCK_AI_DOC_DRAFT

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_generate_club_intro_success(self, _mock):
        """生成社团介绍草稿成功。"""
        client, user = login_as_student("intro_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团介绍"}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"
        assert body["data"]["draft"] == MOCK_AI_DOC_DRAFT

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_generate_with_all_optional_fields(self, _mock):
        """传全部可选字段生成成功。"""
        client, user = login_as_student("full_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({
                "document_type": "社团公告",
                "title_or_topic": "重要通知",
                "main_content": "社团将于本周举办活动",
                "audience": "全体成员",
                "time": "周六下午3点",
                "location": "体育馆",
                "contact": "社长 13800000000",
                "expected_length": "300字",
                "style": "正式",
                "additional_requirements": "需要包含报名链接",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"

    @patch("clubs.views._call_deepseek", side_effect=mock_deepseek_success)
    def test_generate_with_some_optional_fields(self, _mock):
        """传部分可选字段生成成功。"""
        client, user = login_as_student("partial_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({
                "document_type": "招新文案",
                "title_or_topic": "新学期招新",
                "expected_length": "200字",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 200
        body = response_body(resp)
        assert body["code"] == "SUCCESS"


class TestAiDocumentValidation:
    """输入校验测试。"""

    def test_invalid_document_type(self):
        """无效文档类型返回 INVALID_DOCUMENT_TYPE。"""
        client, user = login_as_student("bad_type_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "无效类型"}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "INVALID_DOCUMENT_TYPE"

    def test_missing_document_type(self):
        """缺少 document_type 返回 INVALID_DOCUMENT_TYPE。"""
        client, user = login_as_student("no_type_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "INVALID_DOCUMENT_TYPE"

    def test_empty_document_type(self):
        """空 document_type 返回 INVALID_DOCUMENT_TYPE。"""
        client, user = login_as_student("empty_type_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "   "}),
            content_type="application/json",
        )

        assert resp.status_code == 422
        body = response_body(resp)
        assert body["code"] == "INVALID_DOCUMENT_TYPE"

    def test_get_method_not_allowed(self):
        """GET 请求返回 405。"""
        client, user = login_as_student("get_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.get(f"/api/leader/clubs/{club.id}/ai-documents")

        assert resp.status_code == 405


class TestAiDocumentPermission:
    """权限校验测试。"""

    def test_unauthenticated_rejected(self):
        """未登录返回 UNAUTHENTICATED。"""
        club = create_test_club()
        client = Client()

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 401
        body = response_body(resp)
        assert body["code"] == "UNAUTHENTICATED"

    def test_non_leader_member_rejected(self):
        """普通成员（非负责人）返回 NOT_CLUB_LEADER。"""
        client, user = login_as_student("non_leader")
        club = create_test_club()
        create_test_membership(user, club, club_role="member")

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "NOT_CLUB_LEADER"

    def test_not_club_member_rejected(self):
        """非社团成员返回 NOT_CLUB_LEADER。"""
        client, user = login_as_student("non_member")
        club = create_test_club()
        #不创建成员关系

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "NOT_CLUB_LEADER"

    def test_exited_member_rejected(self):
        """已退出成员返回 NOT_CLUB_LEADER。"""
        client, user = login_as_student("exited")
        club = create_test_club()
        create_test_membership(user, club, member_status="exited")

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "NOT_CLUB_LEADER"

    def test_removed_member_rejected(self):
        """已移除成员返回 NOT_CLUB_LEADER。"""
        client, user = login_as_student("removed")
        club = create_test_club()
        create_test_membership(user, club, member_status="removed")

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "NOT_CLUB_LEADER"

    def test_cancelled_club_rejected(self):
        """已注销社团返回 CLUB_CANCELLED。"""
        from clubs.models import Club

        client, user = login_as_student("cc_leader")
        club = create_test_club()
        club.status = Club.Status.CANCELLED
        club.save()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 409
        body = response_body(resp)
        assert body["code"] == "CLUB_CANCELLED"

    def test_disabled_account_rejected(self):
        """停用账号返回 ACCOUNT_DISABLED。"""
        client, user = login_as_student("disabled_leader")
        club = create_test_club()
        create_test_membership(user, club)
        user.account_status = get_user_model().AccountStatus.DISABLED
        user.save()

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "ACCOUNT_DISABLED"

    def test_admin_cannot_generate(self):
        """管理员不能生成 AI 文档。"""
        client, admin = login_as_admin("ai_admin")
        club = create_test_club()

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "FORBIDDEN"

    def test_cross_club_leader_rejected(self):
        """其他社团的负责人不能生成。"""
        from clubs.models import ClubMembership

        client, user = login_as_student("cross_leader")
        club_a = create_test_club(name="社团A")
        club_b = create_test_club(name="社团B")
        create_test_membership(user, club_a, club_role="leader")
        #同时是社团B的普通成员，但不是负责人
        ClubMembership.objects.create(
            user=user, club=club_b, member_status="active", club_role="member",
        )

        resp = client.post(
            f"/api/leader/clubs/{club_b.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 403
        body = response_body(resp)
        assert body["code"] == "NOT_CLUB_LEADER"


class TestAiDocumentDeepSeekError:
    """DeepSeek 调用失败测试。"""

    def test_no_api_key_configured(self):
        """未配置 API 密钥返回 DEEPSEEK_CALL_FAILED。"""
        client, user = login_as_student("no_key_leader")
        club = create_test_club()
        create_test_membership(user, club)

        with override_settings(DEEPSEEK_API_KEY=""):
            resp = client.post(
                f"/api/leader/clubs/{club.id}/ai-documents",
                data=json.dumps({"document_type": "社团公告"}),
                content_type="application/json",
            )

        assert resp.status_code == 502
        body = response_body(resp)
        assert body["code"] == "DEEPSEEK_CALL_FAILED"

    @patch("clubs.views._call_deepseek")
    def test_deepseek_http_error(self, mock_call):
        """DeepSeek HTTP 错误返回 DEEPSEEK_CALL_FAILED。"""
        from clubs.views import ApiError

        mock_call.side_effect = ApiError(
            code="DEEPSEEK_CALL_FAILED",
            message="DeepSeek API 调用失败（HTTP 500）",
            status=502,
        )

        client, user = login_as_student("http_err_leader")
        club = create_test_club()
        create_test_membership(user, club)

        resp = client.post(
            f"/api/leader/clubs/{club.id}/ai-documents",
            data=json.dumps({"document_type": "社团公告"}),
            content_type="application/json",
        )

        assert resp.status_code == 502
        body = response_body(resp)
        assert body["code"] == "DEEPSEEK_CALL_FAILED"
