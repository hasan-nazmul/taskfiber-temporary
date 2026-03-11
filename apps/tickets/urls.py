from django.urls import path
from . import views

urlpatterns = [
    path('', views.ticket_list, name='ticket_list'),
    path('create/', views.ticket_create, name='ticket_create'),
    path('my/', views.my_tickets, name='my_tickets'),
    path('<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('<int:pk>/edit/', views.ticket_edit, name='ticket_edit'),
    path('<int:pk>/quick-resolve/', views.ticket_quick_resolve, name='ticket_quick_resolve'),

    # API
    path('api/customer-search/', views.customer_search_api, name='customer_search_api'),
]