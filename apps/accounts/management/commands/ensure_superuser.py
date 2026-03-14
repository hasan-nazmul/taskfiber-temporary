import os
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Employee, Role


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ('true', '1', 'yes', 'on')


def next_employee_id(base_value):
    base = (base_value or 'EMP-0001').strip() or 'EMP-0001'
    candidate = base
    counter = 1

    while Employee.objects.filter(employee_id=candidate).exists():
        candidate = f'{base}-{counter:02d}'
        counter += 1

    return candidate


class Command(BaseCommand):
    help = 'Create or update a deploy superuser (and owner employee profile) from env vars.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-password-reset',
            action='store_true',
            help='Reset password for existing user when DJANGO_SUPERUSER_PASSWORD is set.',
        )
        parser.add_argument(
            '--skip-employee',
            action='store_true',
            help='Skip creating/updating the employee profile for the superuser.',
        )

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        first_name = os.environ.get('DJANGO_SUPERUSER_FIRST_NAME', 'System').strip()
        last_name = os.environ.get('DJANGO_SUPERUSER_LAST_NAME', 'Admin').strip()

        if not username:
            self.stdout.write(
                self.style.WARNING(
                    'Skipping superuser bootstrap: DJANGO_SUPERUSER_USERNAME is not set.'
                )
            )
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        created = False

        if user is None:
            if not password:
                self.stdout.write(
                    self.style.WARNING(
                        'Cannot create superuser without DJANGO_SUPERUSER_PASSWORD. Skipping.'
                    )
                )
                return

            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])
            created = True
            self.stdout.write(self.style.SUCCESS(f'Superuser created: {username}'))
        else:
            updated_fields = []

            if not user.is_staff:
                user.is_staff = True
                updated_fields.append('is_staff')
            if not user.is_superuser:
                user.is_superuser = True
                updated_fields.append('is_superuser')
            if email and user.email != email:
                user.email = email
                updated_fields.append('email')
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated_fields.append('first_name')
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated_fields.append('last_name')

            should_reset_password = options['force_password_reset'] or env_bool(
                'DJANGO_SUPERUSER_RESET_PASSWORD',
                False,
            )
            if password and should_reset_password:
                user.set_password(password)
                updated_fields.append('password')

            if updated_fields:
                if 'password' in updated_fields:
                    user.save()
                else:
                    user.save(update_fields=updated_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Superuser updated: {username} ({", ".join(updated_fields)})'
                    )
                )
            else:
                self.stdout.write(f'Superuser already configured: {username}')

        if options['skip_employee']:
            self.stdout.write('Skipping employee profile setup as requested.')
            return

        phone = os.environ.get('DJANGO_SUPERUSER_PHONE', '').strip()
        if not phone:
            self.stdout.write(
                self.style.WARNING(
                    'DJANGO_SUPERUSER_PHONE is not set; employee profile was not created.'
                )
            )
            return

        department = os.environ.get('DJANGO_SUPERUSER_DEPARTMENT', 'management').strip()
        valid_departments = {choice[0] for choice in Employee.DEPARTMENT_CHOICES}
        if department not in valid_departments:
            department = 'management'

        with transaction.atomic():
            owner_role, _ = Role.objects.get_or_create(
                slug='owner',
                defaults={
                    'name': 'Owner',
                    'description': 'System owner with full access',
                },
            )

            if Employee.objects.filter(phone=phone).exclude(user=user).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'Phone {phone} is already used by another employee. '
                        'Skipping employee profile setup.'
                    )
                )
                return

            employee = Employee.objects.filter(user=user).first()
            if employee is None:
                preferred_employee_id = os.environ.get('DJANGO_SUPERUSER_EMPLOYEE_ID', 'EMP-0001')
                employee = Employee.objects.create(
                    user=user,
                    employee_id=next_employee_id(preferred_employee_id),
                    role=owner_role,
                    phone=phone,
                    department=department,
                    date_joined_company=date.today(),
                    is_active=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Owner employee profile created for {username} ({employee.employee_id}).'
                    )
                )
            else:
                employee_updated_fields = []

                if employee.role_id != owner_role.id:
                    employee.role = owner_role
                    employee_updated_fields.append('role')
                if employee.phone != phone:
                    employee.phone = phone
                    employee_updated_fields.append('phone')
                if employee.department != department:
                    employee.department = department
                    employee_updated_fields.append('department')
                if not employee.date_joined_company:
                    employee.date_joined_company = date.today()
                    employee_updated_fields.append('date_joined_company')
                if not employee.employee_id:
                    preferred_employee_id = os.environ.get('DJANGO_SUPERUSER_EMPLOYEE_ID', 'EMP-0001')
                    employee.employee_id = next_employee_id(preferred_employee_id)
                    employee_updated_fields.append('employee_id')
                if not employee.is_active:
                    employee.is_active = True
                    employee_updated_fields.append('is_active')

                if employee_updated_fields:
                    employee.save(update_fields=employee_updated_fields)
                    self.stdout.write(
                        self.style.SUCCESS(
                            'Owner employee profile updated '
                            f'({", ".join(employee_updated_fields)}).'
                        )
                    )
                elif created:
                    self.stdout.write('Owner employee profile already exists and is valid.')
