from django.db import models
from django.contrib.auth.models import User


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Employee(models.Model):
    DEPARTMENT_CHOICES = [
        ('management', 'Management'),
        ('marketing', 'Marketing'),
        ('support', 'Support'),
        ('technical', 'Technical/Cable Team'),
        ('accounts', 'Accounts'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    employee_id = models.CharField(max_length=20, unique=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='employees')
    phone = models.CharField(max_length=15, unique=True, db_index=True)
    whatsapp_number = models.CharField(max_length=15, blank=True)
    nid_number = models.CharField(max_length=20, blank=True, verbose_name='NID Number')
    address = models.TextField(blank=True)

    # Work details
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    date_joined_company = models.DateField()
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    # For field technicians
    assigned_area = models.CharField(max_length=200, blank=True,
                                      help_text='Primarily assigned area for field work')

    profile_photo = models.ImageField(upload_to='employees/', blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def is_manager(self):
        return self.role.slug in ['owner', 'system_admin', 'manager']

    @property
    def is_technician(self):
        return self.role.slug in ['cable_technician', 'field_technician']

    class Meta:
        ordering = ['employee_id']


class ModuleAccess(models.Model):
    ACCESS_LEVELS = [
        ('none', 'No Access'),
        ('view', 'View Only'),
        ('edit', 'View & Edit'),
        ('full', 'Full Access (Delete/Manage)'),
    ]

    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='module_access')
    
    # Granular Module Permissions
    tickets_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    customers_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    zones_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    stock_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    schedule_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    employees_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    teams_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    accounts_finance_access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='none')
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Access Config: {self.employee.full_name}"

    class Meta:
        verbose_name_plural = "Module Access Configurations"

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    leader = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='led_teams')
    members = models.ManyToManyField(Employee, blank=True, related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']