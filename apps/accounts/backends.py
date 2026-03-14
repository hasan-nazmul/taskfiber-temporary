import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from .models import Employee

logger = logging.getLogger(__name__)


class PhoneAuthBackend(ModelBackend):
    """Authenticate using employee phone number instead of username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        try:
            employee = Employee.objects.select_related('user').get(
                phone=username, is_active=True
            )
            user = employee.user
        except Employee.DoesNotExist:
            User().set_password(password)
            user = super().authenticate(request, username=username, password=password, **kwargs)
            if user is None:
                logger.warning('Auth failed: no employee with phone=%s and username fallback failed', username)
            return user

        if not user.check_password(password):
            logger.warning('Auth failed: password mismatch for user=%s (phone=%s)', user.username, username)
            return None

        if not self.user_can_authenticate(user):
            logger.warning('Auth failed: user=%s is inactive (is_active=%s)', user.username, user.is_active)
            return None

        return user
