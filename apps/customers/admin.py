from django.contrib import admin
from .models import Area, Package, Customer


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'zone_code', 'is_active', 'created_at']
    search_fields = ['name', 'zone_code']


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'bandwidth_mbps', 'price', 'package_type', 'is_active']
    list_filter = ['package_type', 'is_active']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'name', 'phone', 'area', 'package', 'status']
    list_filter = ['status', 'area', 'package', 'connection_type']
    search_fields = ['customer_id', 'name', 'phone', 'pppoe_username']