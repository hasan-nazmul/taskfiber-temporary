from django.contrib import admin
from .models import Schedule, Attendance, LeaveRequest


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'shift', 'assigned_area', 'created_by']
    list_filter = ['shift', 'date', 'assigned_area']
    search_fields = ['employee__user__first_name', 'employee__user__last_name']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'status', 'check_in', 'check_out']
    list_filter = ['status', 'date']
    search_fields = ['employee__user__first_name', 'employee__user__last_name']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'leave_type']