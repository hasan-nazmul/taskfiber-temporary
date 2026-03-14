from django.urls import path
from . import views

urlpatterns = [
    path('', views.stock_list, name='stock_list'),
    path('export/csv/', views.stock_export_csv, name='stock_export_csv'),
    path('export/pdf/', views.stock_export_pdf, name='stock_export_pdf'),
    path('import/csv/', views.stock_import_csv, name='stock_import_csv'),
    path('import/template/', views.stock_import_template, name='stock_import_template'),
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