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


#将学生用户序列化为管理员视角的返回字典，字段与 SelfUser 一致但不返回密码哈希。
def serialize_admin_student(user):
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
