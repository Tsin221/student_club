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
