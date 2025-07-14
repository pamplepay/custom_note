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
    list_display = ['customer', 'station', 'visit_date', 'visit_time', 'sale_amount', 'fuel_quantity', 'membership_card']
    list_filter = ['visit_date', 'station', 'payment_type', CustomerFuelFilter]
    search_fields = ['customer__username', 'station__username', 'approval_number', 'membership_card']
    date_hierarchy = 'visit_date'
    ordering = ['-visit_date', '-visit_time']
    
    fieldsets = (
        ('고객 정보', {
            'fields': ('customer', 'station', 'tid')
        }),
        ('방문 정보', {
            'fields': ('visit_date', 'visit_time', 'payment_type', 'product_pack', 'sale_amount', 'fuel_quantity', 'approval_number', 'membership_card')
        }),
        ('시스템 정보', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'station', 'customer__customer_profile') 