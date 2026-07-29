def serialize_self_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "platform_role": user.platform_role,
        "account_status": user.account_status,
        "registered_at": user.registered_at.isoformat(),
        "name": user.name,
        "phone": user.phone,
        "major_class": user.major_class,
        "grade": user.grade,
    }
