"""S13 社团评价 — 后端测试。"""

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


def setup_member_and_club():
    """创建学生、社团、成员关系的快捷函数。"""
    client, student = login_as_student()
    club = create_test_club()
    membership = create_test_membership(student, club)
    return client, student, club, membership


# ═══════════════════════════════════════════════════════════════
# POST /api/clubs/{club_id}/evaluations — 提交评价
# ═══════════════════════════════════════════════════════════════


def test_create_evaluation_success_minimal():
    """仅提供评分即可成功提交评价。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["code"] == "SUCCESS"
    assert body["data"]["rating"] == 4
    assert body["data"]["comment"] is None
    assert body["data"]["user"]["username"] == "test_student"
    assert body["data"]["club"]["name"] == "测试社团"
    assert body["data"]["membership_id"] is not None


def test_create_evaluation_success_full():
    """提供评分和评价内容均可提交。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 5, "comment": "很好的社团！"}),
        content_type="application/json",
    )

    assert resp.status_code == 201
    body = response_body(resp)
    assert body["data"]["rating"] == 5
    assert body["data"]["comment"] == "很好的社团！"


def test_create_evaluation_rating_1_to_5():
    """评分 1-5 均可接受。"""
    client, _student, club, _membership = setup_member_and_club()

    for r in [1, 2, 3, 4, 5]:
        #每个评分需要不同的成员（一条成员关系最多一条评价）
        s = create_student(username=f"student_r{r}")
        client_r = Client()
        login(client_r, f"student_r{r}", "StrongPass!2026")
        create_test_membership(s, club)

        resp = client_r.post(
            f"/api/clubs/{club.id}/evaluations",
            data=json.dumps({"rating": r}),
            content_type="application/json",
        )
        assert resp.status_code == 201, f"rating={r} should be accepted"


def test_create_evaluation_rating_out_of_range():
    """评分超出 1-5 返回 INVALID_RATING。"""
    client, _student, club, _membership = setup_member_and_club()

    for invalid in [0, 6, -1, 10]:
        #需要新成员
        s = create_student(username=f"student_inv{invalid}")
        client_r = Client()
        login(client_r, f"student_inv{invalid}", "StrongPass!2026")
        create_test_membership(s, club)

        resp = client_r.post(
            f"/api/clubs/{club.id}/evaluations",
            data=json.dumps({"rating": invalid}),
            content_type="application/json",
        )
        assert resp.status_code in (400, 422)
        body = response_body(resp)
        assert body["code"] == "INVALID_RATING"


def test_create_evaluation_missing_rating():
    """缺少评分字段返回 INVALID_RATING。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"comment": "不错"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_RATING"


def test_create_evaluation_rating_not_int():
    """评分不是整数返回 INVALID_RATING。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": "4"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_RATING"


def test_create_evaluation_duplicate():
    """同一成员关系重复评价返回 DUPLICATE_EVALUATION。"""
    client, _student, club, _membership = setup_member_and_club()

    #第一次成功
    resp1 = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    assert resp1.status_code == 201

    #第二次重复
    resp2 = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 5}),
        content_type="application/json",
    )
    assert resp2.status_code == 409
    assert response_body(resp2)["code"] == "DUPLICATE_EVALUATION"


def test_create_evaluation_non_member():
    """非社团成员不能评价。"""
    client, student = login_as_student()
    club = create_test_club()
    #不创建成员关系

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_CLUB_MEMBER"


def test_create_evaluation_ex_member():
    """已退出的成员不能评价。"""
    client, student, club, membership = setup_member_and_club()

    #退出社团
    membership.member_status = "exited"
    membership.save()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "MEMBERSHIP_INACTIVE"


def test_create_evaluation_cancelled_club():
    """已注销社团不能评价。"""
    client, _student, club, _membership = setup_member_and_club()

    club.status = "cancelled"
    club.save()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_create_evaluation_unauthenticated():
    """未登录不能评价。"""
    _client, _student, club, _membership = setup_member_and_club()

    anon_client = Client()
    resp = anon_client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_create_evaluation_rejects_disallowed_fields():
    """提交不允许的字段返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3, "status": "已审核"}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_create_evaluation_leader_can_evaluate():
    """负责人也可以评价自己负责的社团。"""
    client, student = login_as_student(username="leader1")
    club = create_test_club()
    create_test_membership(student, club, club_role="leader")

    resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 201


# ═══════════════════════════════════════════════════════════════
# GET /api/me/evaluations — 查看本人评价
# ═══════════════════════════════════════════════════════════════


def test_my_evaluations_empty():
    """没有评价时返回空列表。"""
    client, _student, _club, _membership = setup_member_and_club()

    resp = client.get("/api/me/evaluations")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["items"] == []


def test_my_evaluations_with_data():
    """评价后可以在列表看到。"""
    client, _student, club, _membership = setup_member_and_club()

    #提交评价
    client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 4, "comment": "好"}),
        content_type="application/json",
    )

    resp = client.get("/api/me/evaluations")
    assert resp.status_code == 200
    body = response_body(resp)
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["rating"] == 4
    assert body["data"]["items"][0]["comment"] == "好"


def test_my_evaluations_shows_history():
    """退出社团后仍可查看历史评价。"""
    client, _student, club, membership = setup_member_and_club()

    #先提交评价
    client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    #退出社团
    membership.member_status = "exited"
    membership.save()

    #仍可查看历史评价
    resp = client.get("/api/me/evaluations")
    assert resp.status_code == 200
    assert len(response_body(resp)["data"]["items"]) == 1


def test_my_evaluations_unauthenticated():
    """未登录不能查看评价。"""
    resp = Client().get("/api/me/evaluations")
    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_my_evaluations_only_own():
    """只返回本人的评价，不返回他人评价。"""
    client1, _student1, club, _membership1 = setup_member_and_club()

    #另一个学生
    student2 = create_student(username="student_02")
    client2 = Client()
    login(client2, "student_02", "StrongPass!2026")
    create_test_membership(student2, club)

    #各自评价
    client1.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 5}),
        content_type="application/json",
    )
    client2.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 1}),
        content_type="application/json",
    )

    #学生1只看到自己
    resp1 = client1.get("/api/me/evaluations")
    items1 = response_body(resp1)["data"]["items"]
    assert len(items1) == 1
    assert items1[0]["user"]["username"] == "test_student"

    #学生2只看到自己
    resp2 = client2.get("/api/me/evaluations")
    items2 = response_body(resp2)["data"]["items"]
    assert len(items2) == 1
    assert items2[0]["user"]["username"] == "student_02"


# ═══════════════════════════════════════════════════════════════
# PATCH /api/me/evaluations/{evaluation_id} — 修改本人评价
# ═══════════════════════════════════════════════════════════════


def test_update_evaluation_success():
    """本人修改评分和内容成功。"""
    client, _student, club, _membership = setup_member_and_club()

    #先提交评价
    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3, "comment": "还行"}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    #修改评价
    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 5, "comment": "非常棒"}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["rating"] == 5
    assert body["data"]["comment"] == "非常棒"


def test_update_evaluation_rating_only():
    """只修改评分。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 2, "comment": "一般"}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["rating"] == 4
    assert body["data"]["comment"] == "一般"  #未修改


def test_update_evaluation_comment_only():
    """只修改评价内容。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3, "comment": "还行"}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"comment": "更新后的评价"}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["rating"] == 3  #未修改
    assert body["data"]["comment"] == "更新后的评价"


def test_update_evaluation_clear_comment():
    """将评价内容清空（设置为 null）。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3, "comment": "还行"}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"comment": ""}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert response_body(resp)["data"]["comment"] is None


def test_update_evaluation_not_owner():
    """非本人不能修改评价。"""
    client1, _student1, club, _membership1 = setup_member_and_club()

    #学生2
    student2 = create_student(username="stu2")
    client2 = Client()
    login(client2, "stu2", "StrongPass!2026")
    create_test_membership(student2, club)

    #学生1提交评价
    create_resp = client1.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    #学生2尝试修改学生1的评价
    resp = client2.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 1}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "NOT_EVALUATION_OWNER"


def test_update_evaluation_not_found():
    """修改不存在的评价返回 RESOURCE_NOT_FOUND。"""
    client, _student, _club, _membership = setup_member_and_club()

    resp = client.patch(
        "/api/me/evaluations/99999",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    assert resp.status_code == 404
    assert response_body(resp)["code"] == "RESOURCE_NOT_FOUND"


def test_update_evaluation_ex_member():
    """已退出成员不能修改评价。"""
    client, _student, club, membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    #退出社团
    membership.member_status = "exited"
    membership.save()

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    assert response_body(resp)["code"] == "MEMBERSHIP_INACTIVE"


def test_update_evaluation_cancelled_club():
    """已注销社团的评价不能修改。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    club.status = "cancelled"
    club.save()

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 409
    assert response_body(resp)["code"] == "CLUB_CANCELLED"


def test_update_evaluation_rating_out_of_range():
    """修改评分超出范围返回 INVALID_RATING。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 6}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_RATING"


def test_update_evaluation_empty_body():
    """空请求体返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_update_evaluation_rejects_disallowed_fields():
    """修改不允许的字段返回错误。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 4, "membership_id": 99}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert response_body(resp)["code"] == "INVALID_REQUEST"


def test_update_evaluation_unauthenticated():
    """未登录不能修改评价。"""
    _client, _student, club, _membership = setup_member_and_club()

    create_resp = _client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    anon_client = Client()
    resp = anon_client.patch(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_update_evaluation_wrong_method():
    """不支持的 HTTP 方法返回 405。"""
    client, _student, club, _membership = setup_member_and_club()

    create_resp = client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )
    evaluation_id = response_body(create_resp)["data"]["id"]

    resp = client.put(
        f"/api/me/evaluations/{evaluation_id}",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    assert resp.status_code == 405


# ═══════════════════════════════════════════════════════════════
# GET /api/admin/evaluations — 管理员查看全部评价
# ═══════════════════════════════════════════════════════════════


def test_admin_evaluations_empty():
    """管理员查看空评价列表。"""
    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    resp = admin_client.get("/api/admin/evaluations")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


def test_admin_evaluations_with_data():
    """管理员可以看到所有评价。"""
    #学生1评价
    client1, _student1, club1, _membership1 = setup_member_and_club()
    client1.post(
        f"/api/clubs/{club1.id}/evaluations",
        data=json.dumps({"rating": 4}),
        content_type="application/json",
    )

    #学生2评价另一个社团
    club2 = create_test_club(name="社团2")
    student2 = create_student(username="stu_eval")
    client2 = Client()
    login(client2, "stu_eval", "StrongPass!2026")
    create_test_membership(student2, club2)
    client2.post(
        f"/api/clubs/{club2.id}/evaluations",
        data=json.dumps({"rating": 2, "comment": "不太好"}),
        content_type="application/json",
    )

    #管理员查看
    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    resp = admin_client.get("/api/admin/evaluations")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["total"] == 2
    assert len(body["data"]["items"]) == 2


def test_admin_evaluations_pagination():
    """管理员评价列表分页正常。"""
    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    resp = admin_client.get("/api/admin/evaluations?page=1&page_size=10")
    assert resp.status_code == 200
    body = response_body(resp)
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 10


def test_admin_evaluations_non_admin():
    """非管理员不能查看全部评价。"""
    client, _student, _club, _membership = setup_member_and_club()

    resp = client.get("/api/admin/evaluations")
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "FORBIDDEN"


def test_admin_evaluations_unauthenticated():
    """未登录不能查看管理员评价列表。"""
    resp = Client().get("/api/admin/evaluations")
    assert resp.status_code == 401
    assert response_body(resp)["code"] == "UNAUTHENTICATED"


def test_admin_cannot_create_evaluation():
    """管理员不能提交评价（只有学生成员可以）。"""
    admin = create_admin()
    admin_client = Client()
    login(admin_client, "admin_test", "AdminPass!2026")

    club = create_test_club()

    resp = admin_client.post(
        f"/api/clubs/{club.id}/evaluations",
        data=json.dumps({"rating": 3}),
        content_type="application/json",
    )

    #管理员账号不是学生，require_club_member 中的 require_active_student 会拒绝
    assert resp.status_code == 403
    assert response_body(resp)["code"] == "FORBIDDEN"
