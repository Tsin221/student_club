from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class SessionUserBackend(ModelBackend):
    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model._default_manager.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
