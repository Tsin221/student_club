from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

#自定义认证后端，基于 session 中的 user_id 获取用户对象。
class SessionUserBackend(ModelBackend):
    #根据主键获取用户实例，若不存在则返回 None。
    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model._default_manager.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
