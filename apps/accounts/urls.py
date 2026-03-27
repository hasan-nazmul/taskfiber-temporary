from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Auth - using simple paths
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('profile/', views.profile, name='profile'),
    path('change-password/', views.change_password, name='change_password'),

    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/export/csv/', views.employee_export_csv, name='employee_export_csv'),
    path('employees/export/pdf/', views.employee_export_pdf, name='employee_export_pdf'),
    path('employees/import/csv/', views.employee_import_csv, name='employee_import_csv'),
    path('employees/import/template/', views.employee_import_template, name='employee_import_template'),
    path('employees/add/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/access/', views.employee_module_access, name='employee_module_access'),

    # Teams
    path('teams/', views.team_list, name='team_list'),
    path('teams/add/', views.team_create, name='team_create'),
    path('teams/<int:pk>/edit/', views.team_edit, name='team_edit'),
]