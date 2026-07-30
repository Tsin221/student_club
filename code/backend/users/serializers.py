#将当前登录用户对象序列化为字典，返回个人用户信息。
def serialize_self_user(user):
    return {
        #基础身份
        "id": user.id,
        "username": user.username,
        "platform_role": user.platform_role,
        #账号状态
        "account_status": user.account_status,
        "registered_at": user.registered_at.isoformat(),
        #个人资料
        "name": user.name,
        "phone": user.phone,
        "major_class": user.major_class,
        "grade": user.grade,
    }
