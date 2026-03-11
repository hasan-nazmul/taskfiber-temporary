from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Auth - using simple paths
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),

    # Employees
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/access/', views.employee_module_access, name='employee_module_access'),

    # Teams
    path('teams/', views.team_list, name='team_list'),
    path('teams/add/', views.team_create, name='team_create'),
    path('teams/<int:pk>/edit/', views.team_edit, name='team_edit'),
]