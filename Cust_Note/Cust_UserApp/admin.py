from django.contrib import admin
from .models import CustomerVisitHistory

class CustomerFuelFilter(admin.SimpleListFilter):
    title = '주유량 범위'
    parameter_name = 'fuel_range'

    def lookups(self, request, model_admin):
        return (
            ('0', '0L'),
            ('1-10', '1-10L'),
            ('10-50', '10-50L'),
            ('50-100', '50-100L'),
            ('100+', '100L 이상'),
        )

    def queryset(self, request, queryset):
        if self.value() == '0':
            return queryset.filter(customer__customer_profile__total_fuel_amount=0)
        elif self.value() == '1-10':
            return queryset.filter(customer__customer_profile__total_fuel_amount__gt=0, customer__customer_profile__total_fuel_amount__lte=10)
        elif self.value() == '10-50':
            return queryset.filter(customer__customer_profile__total_fuel_amount__gt=10, customer__customer_profile__total_fuel_amount__lte=50)
        elif self.value() == '50-100':
            return queryset.filter(customer__customer_profile__total_fuel_amount__gt=50, customer__customer_profile__total_fuel_amount__lte=100)
        elif self.value() == '100+':
            return queryset.filter(customer__customer_profile__total_fuel_amount__gt=100)
        return queryset

@admin.register(CustomerVisitHistory)
class CustomerVisitHistoryAdmin(admin.ModelAdmin):
    list_display = ['customer', 'station', 'visit_date', 'visit_time', 'sale_amount', 'visit_count', 'monthly_visit_count', 'customer_total_fuel', 'customer_monthly_fuel', 'customer_last_fuel']
    list_filter = ['visit_date', 'station', 'payment_type', CustomerFuelFilter]
    search_fields = ['customer__username', 'station__username', 'approval_number']
    date_hierarchy = 'visit_date'
    ordering = ['-visit_date', '-visit_time']
    
    fieldsets = (
        ('고객 정보', {
            'fields': ('customer', 'station', 'tid')
        }),
        ('방문 정보', {
            'fields': ('visit_date', 'visit_time', 'payment_type', 'product_pack', 'sale_amount', 'approval_number')
        }),
        ('방문 횟수', {
            'fields': ('visit_count', 'monthly_visit_count')
        }),
        ('시스템 정보', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['visit_count', 'monthly_visit_count', 'created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'station', 'customer__customer_profile')
    
    def customer_total_fuel(self, obj):
        """고객의 총 주유량"""
        try:
            if hasattr(obj.customer, 'customer_profile') and obj.customer.customer_profile:
                return f"{obj.customer.customer_profile.total_fuel_amount:.2f}L"
            return "0.00L"
        except Exception:
            return "0.00L"
    customer_total_fuel.short_description = '총 주유량'
    customer_total_fuel.admin_order_field = 'customer__customer_profile__total_fuel_amount'
    
    def customer_monthly_fuel(self, obj):
        """고객의 월 주유량"""
        try:
            if hasattr(obj.customer, 'customer_profile') and obj.customer.customer_profile:
                return f"{obj.customer.customer_profile.monthly_fuel_amount:.2f}L"
            return "0.00L"
        except Exception:
            return "0.00L"
    customer_monthly_fuel.short_description = '월 주유량'
    customer_monthly_fuel.admin_order_field = 'customer__customer_profile__monthly_fuel_amount'
    
    def customer_last_fuel(self, obj):
        """고객의 최근 주유량"""
        try:
            if hasattr(obj.customer, 'customer_profile') and obj.customer.customer_profile:
                return f"{obj.customer.customer_profile.last_fuel_amount:.2f}L"
            return "0.00L"
        except Exception:
            return "0.00L"
    customer_last_fuel.short_description = '최근 주유량'
    customer_last_fuel.admin_order_field = 'customer__customer_profile__last_fuel_amount' 