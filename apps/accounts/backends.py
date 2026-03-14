from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from .models import Employee


class PhoneAuthBackend(ModelBackend):
    """Authenticate using employee phone number instead of username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        # username param actually holds the phone number from the login form
        if not username or not password:
            return None

        try:
            employee = Employee.objects.select_related('user').get(
                phone=username, is_active=True
            )
            user = employee.user
        except Employee.DoesNotExist:
            # Run the default password hasher to prevent timing attacks
            User().set_password(password)
            # Fallback allows admin/superuser login by username when no employee profile exists.
            return super().authenticate(request, username=username, password=password, **kwargs)

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
