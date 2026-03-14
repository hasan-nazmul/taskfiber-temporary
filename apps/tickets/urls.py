from django.urls import path
from . import views

urlpatterns = [
    path('', views.ticket_list, name='ticket_list'),
    path('export/csv/', views.ticket_export_csv, name='ticket_export_csv'),
    path('export/pdf/', views.ticket_export_pdf, name='ticket_export_pdf'),
    path('import/csv/', views.ticket_import_csv, name='ticket_import_csv'),
    path('import/template/', views.ticket_import_template, name='ticket_import_template'),
    path('create/', views.ticket_create, name='ticket_create'),
    path('my/', views.my_tickets, name='my_tickets'),
    path('<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('<int:pk>/edit/', views.ticket_edit, name='ticket_edit'),
    path('<int:pk>/quick-resolve/', views.ticket_quick_resolve, name='ticket_quick_resolve'),

    # API
    path('api/customer-search/', views.customer_search_api, name='customer_search_api'),
]