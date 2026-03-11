from django.urls import path
from . import views

urlpatterns = [
    # Customers
    path('', views.customer_list, name='customer_list'),
    path('add/', views.customer_create, name='customer_create'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    path('<int:pk>/edit/', views.customer_edit, name='customer_edit'),

    # Areas / Zones
    path('areas/', views.area_list, name='area_list'),
    path('areas/add/', views.area_create, name='area_create'),
    path('areas/<int:pk>/edit/', views.area_edit, name='area_edit'),
    path('areas/<int:pk>/toggle-active/', views.area_toggle_active, name='area_toggle_active'),

    # Packages
    path('packages/', views.package_list, name='package_list'),
    path('packages/add/', views.package_create, name='package_create'),
    path('packages/<int:pk>/edit/', views.package_edit, name='package_edit'),
]