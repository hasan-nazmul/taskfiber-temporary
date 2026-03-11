from django.contrib import admin
from .models import Role, Employee


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'full_name', 'role', 'department', 'phone', 'is_active']
    list_filter = ['role', 'department', 'is_active']
    search_fields = ['user__first_name', 'user__last_name', 'employee_id', 'phone']