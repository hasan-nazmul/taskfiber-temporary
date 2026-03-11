from django.urls import path
from . import views

urlpatterns = [
    # Schedule
    path('', views.schedule_view, name='schedule_view'),
    path('assign/', views.schedule_assign, name='schedule_assign'),
    path('bulk-assign/', views.schedule_bulk_assign, name='schedule_bulk_assign'),
    path('<int:pk>/delete/', views.schedule_delete, name='schedule_delete'),

    # Attendance
    path('attendance/', views.attendance_mark, name='attendance_mark'),
    path('attendance/report/', views.attendance_report, name='attendance_report'),

    # Leave
    path('leave/', views.leave_request_list, name='leave_request_list'),
    path('leave/create/', views.leave_request_create, name='leave_request_create'),
    path('leave/<int:pk>/approve/', views.leave_request_approve, name='leave_request_approve'),
]