from django.contrib import admin
from .models import StockCategory, StockItem, StockTransaction


@admin.register(StockCategory)
class StockCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = [
        'sku', 'name', 'category', 'quantity_in_stock',
        'minimum_stock_level', 'purchase_price', 'is_active'
    ]
    list_filter = ['category', 'is_active', 'unit']
    search_fields = ['name', 'sku', 'brand', 'model_number']


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'stock_item', 'transaction_type', 'quantity',
        'performed_by', 'created_at'
    ]
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['stock_item__name', 'vendor_name', 'invoice_number']