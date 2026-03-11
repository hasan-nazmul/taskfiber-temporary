from django.urls import path
from . import views

urlpatterns = [
    path('', views.stock_list, name='stock_list'),
    path('add/', views.stock_item_create, name='stock_item_create'),
    path('<int:pk>/', views.stock_item_detail, name='stock_item_detail'),
    path('<int:pk>/edit/', views.stock_item_edit, name='stock_item_edit'),

    # Transactions
    path('purchase/', views.stock_purchase, name='stock_purchase'),
    path('issue/', views.stock_issue, name='stock_issue'),
    path('return/', views.stock_return, name='stock_return'),
    path('adjustment/', views.stock_adjustment, name='stock_adjustment'),
    path('transactions/', views.stock_transactions, name='stock_transactions'),

    # Categories
    path('categories/', views.stock_category_list, name='stock_category_list'),
    path('categories/add/', views.stock_category_create, name='stock_category_create'),
    path('categories/<int:pk>/edit/', views.stock_category_edit, name='stock_category_edit'),
]