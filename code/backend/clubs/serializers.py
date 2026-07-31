#将 Club 对象序列化为字典。
def serialize_club(club):
    return {
        "id": club.id,
        "name": club.name,
        "category": club.category,
        "introduction": club.introduction,
        "logo": f"/media/{club.logo}" if club.logo else "",
        "created_at": club.created_at.isoformat(),
        "status": club.status,
    }


#将成员关系序列化为管理员视角的返回字典。
def serialize_membership_for_admin(membership):
    user = membership.user
    return {
        "id": membership.id,
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "phone": user.phone,
            "major_class": user.major_class,
            "grade": user.grade,
            "account_status": user.account_status,
        },
        "club": {
            "id": membership.club.id,
            "name": membership.club.name,
            "status": membership.club.status,
        },
        "member_status": membership.member_status,
        "club_role": membership.club_role,
    }


#将成员关系序列化为负责人视角的返回字典。
def serialize_membership_for_leader(membership):
    user = membership.user
    return {
        "id": membership.id,
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "phone": user.phone,
            "major_class": user.major_class,
            "grade": user.grade,
            "account_status": user.account_status,
        },
        "club_id": membership.club_id,
        "member_status": membership.member_status,
        "club_role": membership.club_role,
    }


#将成员关系序列化为本人视角的返回字典。
def serialize_my_membership(membership):
    club = membership.club
    return {
        "id": membership.id,
        "club": {
            "id": club.id,
            "name": club.name,
            "category": club.category,
            "logo": f"/media/{club.logo}" if club.logo else "",
            "status": club.status,
        },
        "member_status": membership.member_status,
        "club_role": membership.club_role,
    }


#计算招新的实时展示状态和已通过人数，返回 (display_status, approved_count)。
def compute_recruitment_status(recruitment):
    from django.utils import timezone

    now = timezone.now()

    approved_count = recruitment.join_applications.filter(status="已通过").count()

    #展示状态计算（优先级从高到低）
    if recruitment.ended_early or now >= recruitment.end_time:
        display_status = "已结束"
    elif approved_count >= recruitment.capacity:
        display_status = "已满"
    elif now < recruitment.start_time:
        display_status = "未开始"
    else:
        display_status = "进行中"

    return display_status, approved_count


#将 Recruitment 对象序列化为字典。
def serialize_recruitment(recruitment):
    display_status, approved_count = compute_recruitment_status(recruitment)
    return {
        "id": recruitment.id,
        "title": recruitment.title,
        "introduction": recruitment.introduction,
        "requirements": recruitment.requirements,
        "capacity": recruitment.capacity,
        "start_time": recruitment.start_time.isoformat(),
        "end_time": recruitment.end_time.isoformat(),
        "club_id": recruitment.club_id,
        "publisher": {
            "id": recruitment.publisher.id,
            "username": recruitment.publisher.username,
        },
        "published_at": recruitment.published_at.isoformat(),
        "ended_early": recruitment.ended_early,
        "display_status": display_status,
        "approved_count": approved_count,
    }


# ── S07：入社申请与通知序列化 ──────────────────────────────


#将 JoinApplication 对象序列化为字典。
def serialize_join_application(app):
    return {
        "id": app.id,
        "applicant_id": app.applicant_id,
        "applicant_name_snapshot": app.applicant_name_snapshot,
        "applicant_major_class_snapshot": app.applicant_major_class_snapshot,
        "club": {
            "id": app.club.id,
            "name": app.club.name,
        },
        "recruitment": {
            "id": app.recruitment.id,
            "title": app.recruitment.title,
        },
        "reason": app.reason,
        "applied_at": app.applied_at.isoformat(),
        "status": app.status,
    }


#将 Notification 对象序列化为字典。
def serialize_notification(notification):
    return {
        "id": notification.id,
        "type": notification.type,
        "content": notification.content,
    }
