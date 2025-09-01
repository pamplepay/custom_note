from django.contrib import admin
from .models import StationBusinessInfo, ProductInfo, TankInfo

# Register your models here.

@admin.register(StationBusinessInfo)
class StationBusinessInfoAdmin(admin.ModelAdmin):
    list_display = ['station_name', 'representative_name', 'business_registration_number', 'phone_number', 'refinery_company', 'created_at']
    list_filter = ['refinery_company', 'created_at', 'updated_at']
    search_fields = ['station_name', 'representative_name', 'business_registration_number', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('사용자 정보', {
            'fields': ('user',)
        }),
        ('기본 정보', {
            'fields': ('station_name', 'representative_name', 'business_registration_number', 'sub_business_number')
        }),
        ('주소 정보', {
            'fields': ('business_address',)
        }),
        ('사업 정보', {
            'fields': ('business_type', 'business_category')
        }),
        ('연락처', {
            'fields': ('phone_number',)
        }),
        ('석유 관련 정보', {
            'fields': ('refinery_company', 'petroleum_management_code', 'oil_code')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ['item_code', 'item_name', 'product_category', 'inventory_management', 'user', 'created_at']
    list_filter = ['product_category', 'inventory_management', 'created_at', 'updated_at']
    search_fields = ['item_code', 'item_name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('사용자 정보', {
            'fields': ('user',)
        }),
        ('상품 정보', {
            'fields': ('item_code', 'item_name', 'product_category', 'inventory_management')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TankInfo)
class TankInfoAdmin(admin.ModelAdmin):
    list_display = ['tank_code', 'tank_number', 'fuel_type', 'permitted_capacity', 'user', 'created_at']
    list_filter = ['fuel_type', 'created_at', 'updated_at']
    search_fields = ['tank_code', 'tank_number', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('사용자 정보', {
            'fields': ('user',)
        }),
        ('탱크 정보', {
            'fields': ('tank_code', 'tank_number', 'fuel_type', 'permitted_capacity')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
