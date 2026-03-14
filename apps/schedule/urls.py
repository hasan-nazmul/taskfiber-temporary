from django.urls import path
from . import views

urlpatterns = [
    # Schedule
    path('', views.schedule_view, name='schedule_view'),
    path('export/csv/', views.schedule_export_csv, name='schedule_export_csv'),
    path('export/pdf/', views.schedule_export_pdf, name='schedule_export_pdf'),
    path('import/csv/', views.schedule_import_csv, name='schedule_import_csv'),
    path('import/template/', views.schedule_import_template, name='schedule_import_template'),
    path('assign/', views.schedule_assign, name='schedule_assign'),
    path('<int:pk>/edit/', views.schedule_edit, name='schedule_edit'),
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