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


# ── S09：社团公告序列化 ────────────────────────────────────


#将 Announcement 对象序列化为字典。
def serialize_announcement(announcement):
    return {
        "id": announcement.id,
        "title": announcement.title,
        "content": announcement.content,
        "club_id": announcement.club_id,
        "publisher": {
            "id": announcement.publisher.id,
            "username": announcement.publisher.username,
        },
        "published_at": announcement.published_at.isoformat(),
        "is_pinned": announcement.is_pinned,
        "status": announcement.status,
    }


# ── S11：帖子回复序列化 ──────────────────────────────────────


def serialize_reply(reply):
    """将 Reply 对象序列化为字典。"""
    return {
        "id": reply.id,
        "content": reply.content,
        "post_id": reply.post_id,
        "author": {
            "id": reply.author.id,
            "username": reply.author.username,
        },
        "status": reply.status,
    }


# ── S13：社团评价序列化 ────────────────────────────────────


def serialize_club_evaluation(evaluation):
    """将 ClubEvaluation 对象序列化为字典。"""
    return {
        "id": evaluation.id,
        "user": {
            "id": evaluation.user.id,
            "username": evaluation.user.username,
        },
        "club": {
            "id": evaluation.club.id,
            "name": evaluation.club.name,
        },
        "membership_id": evaluation.membership_id,
        "rating": evaluation.rating,
        "comment": evaluation.comment,
    }


# ── S14：意见反馈 ────────────────────────────────────────────


def serialize_feedback(feedback):
    """将 Feedback 对象序列化为字典。"""
    return {
        "id": feedback.id,
        "submitter": {
            "id": feedback.submitter.id,
            "username": feedback.submitter.username,
        },
        "club": {
            "id": feedback.club.id,
            "name": feedback.club.name,
        },
        "content": feedback.content,
        "submitted_at": feedback.submitted_at.isoformat(),
        "status": feedback.status,
        "processing_note": feedback.processing_note,
    }


def serialize_post(post, current_user_id=None):
    """将 Post 对象序列化为字典。

    like_count 和 liked_by_me 实时计算：
    - S10 阶段 post_like 表尚未建立，暂返回 0／False。
    - S12 引入 post_like 后改为从关联表实时统计。
    """
    like_count = post.post_likes.count()
    liked_by_me = (
        current_user_id is not None
        and post.post_likes.filter(user_id=current_user_id).exists()
    )

    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "club_id": post.club_id,
        "author": {
            "id": post.author.id,
            "username": post.author.username,
        },
        "is_pinned": post.is_pinned,
        "status": post.status,
        "like_count": like_count,
        "liked_by_me": liked_by_me,
    }
