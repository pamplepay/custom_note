from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.auth.hashers import make_password
from .models import CustomUser, CustomerProfile, StationProfile, CustomerStationRelation
from OilNote_StationApp.models import CustomerCoupon
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages

User = get_user_model()

# 프록시 모델 추가
class CustomerUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = '일반 고객'
        verbose_name_plural = '1. 일반 고객들'

class StationUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = '주유소 고객들'
        verbose_name_plural = '2. 주유소 고객들'

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'user_type')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = '__all__'

class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    verbose_name_plural = '3. 고객 프로필'
    extra = 0
    fields = ('name', 'customer_phone', 'car_number', 'car_model', 'fuel_type', 'membership_card', 'group', 'total_fuel_amount', 'monthly_fuel_amount', 'last_fuel_amount', 'total_fuel_cost', 'monthly_fuel_cost', 'last_fuel_cost', 'last_fuel_date')

class StationProfileInline(admin.StackedInline):
    model = StationProfile
    can_delete = False
    verbose_name_plural = '4. 주유소 프로필'
    extra = 0

class CustomerStationInline(admin.TabularInline):
    model = CustomerStationRelation
    fk_name = 'customer'
    extra = 0
    verbose_name = '등록된 주유소'
    verbose_name_plural = '등록된 주유소 목록'
    can_delete = True
    min_num = 0
    max_num = None
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(customer__user_type='CUSTOMER')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        # 폼 필드를 선택적으로 만들기
        for field in formset.form.base_fields.values():
            field.required = False
        
        # 폼 검증 완전 비활성화
        def clean_form(self):
            # station이 비어있으면 검증 건너뛰기
            if not self.cleaned_data.get('station'):
                return self.cleaned_data
            try:
                return super(formset.form, self).clean()
            except:
                # 모든 검증 오류 무시
                return self.cleaned_data
        
        # 폼셋 검증 완전 비활성화
        def clean_formset(self):
            # 빈 폼은 모두 건너뛰기
            cleaned_data = []
            for form in self.forms:
                # 폼이 삭제되었거나 빈 경우 건너뛰기
                if form.instance.pk is None:
                    # 새로 생성되는 폼의 경우, station 필드가 비어있으면 건너뛰기
                    if not form.cleaned_data.get('station'):
                        continue
                cleaned_data.append(form.cleaned_data)
            return cleaned_data
        
        formset.form.clean = clean_form
        formset.clean = clean_formset
        return formset

class CustomerCouponInline(admin.TabularInline):
    model = CustomerCoupon
    fk_name = 'customer'
    extra = 0
    verbose_name = '보유 쿠폰'
    verbose_name_plural = '보유 쿠폰 목록'
    readonly_fields = ('issued_date', 'used_date', 'expiry_date', 'status_display')
    fields = ('coupon_template', 'status_display', 'issued_date', 'used_date', 'expiry_date')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('coupon_template__station')
    
    def status_display(self, obj):
        """쿠폰 상태를 색상으로 표시"""
        status_colors = {
            'AVAILABLE': '#28a745',
            'USED': '#6c757d',
            'EXPIRED': '#dc3545'
        }
        status_names = {
            'AVAILABLE': '사용가능',
            'USED': '사용완료',
            'EXPIRED': '만료됨'
        }
        color = status_colors.get(obj.status, '#6c757d')
        name = status_names.get(obj.status, obj.status)
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, name)
    status_display.short_description = '상태'

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    
    list_display = (
        'username', 
        'email', 
        'user_type', 
        'backup_password_display',
        'is_active', 
        'date_joined',
        'reset_password_button'
    )
    list_filter = ('user_type', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email')
    ordering = ('-date_joined',)
    
    # fieldsets를 사용하여 권한 필드들을 맨 아래에 배치
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('개인정보', {'fields': ('first_name', 'last_name', 'email')}),
        ('사용자 타입', {'fields': ('user_type',)}),
        ('백업 정보', {'fields': ('pw_back',)}),
        ('중요한 날짜', {'fields': ('last_login', 'date_joined')}),
        ('권한', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),  # 접을 수 있도록 설정
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'user_type', 'password1', 'password2'),
        }),
    )
    
    actions = ['reset_password', 'restore_backup_password', 'activate_users', 'deactivate_users']
    
    def get_inlines(self, request, obj):
        if obj:
            if obj.user_type == 'CUSTOMER':
                return [CustomerProfileInline, CustomerStationInline, CustomerCouponInline]
            elif obj.user_type == 'STATION':
                return [StationProfileInline]
        return []
    
    def backup_password_display(self, obj):
        """백업 패스워드 표시"""
        if obj.pw_back:
            return "●●●●"  # 백업 있음을 표시
        return "없음"
    backup_password_display.short_description = "백업 PW"
    
    def reset_password(self, request, queryset):
        for user in queryset:
            new_password = '1111'
            user.password = make_password(new_password)
            user.pw_back = new_password  # 실제 비밀번호 값을 저장
            user.save()
        self.message_user(request, f"{queryset.count()}명의 사용자 비밀번호가 '1111'로 초기화되었습니다.")
    reset_password.short_description = "선택된 사용자의 비밀번호를 '1111'로 초기화"
    
    def restore_backup_password(self, request, queryset):
        """선택된 사용자들의 패스워드를 백업에서 복원"""
        updated = 0
        failed = 0
        for user in queryset:
            if user.pw_back:
                user.set_password(user.pw_back)  # 백업된 실제 비밀번호 값을 사용
                user.save()
                updated += 1
            else:
                failed += 1
        
        message = f'{updated}명의 사용자 패스워드가 백업에서 복원되었습니다.'
        if failed > 0:
            message += f' ({failed}명은 백업 패스워드가 없습니다.)'
        
        self.message_user(request, message)
    restore_backup_password.short_description = "백업 패스워드로 복원"
    
    def activate_users(self, request, queryset):
        """선택된 사용자들을 활성화"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated}명의 사용자가 활성화되었습니다.')
    activate_users.short_description = "선택된 사용자 활성화"
    
    def deactivate_users(self, request, queryset):
        """선택된 사용자들을 비활성화"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated}명의 사용자가 비활성화되었습니다.')
    deactivate_users.short_description = "선택된 사용자 비활성화"

    def reset_password_button(self, obj):
        """비밀번호 초기화 버튼을 표시"""
        return format_html(
            '<a class="button" href="{}">비밀번호 초기화</a>',
            f'reset-password/{obj.id}/'
        )
    reset_password_button.short_description = '비밀번호 초기화'
    reset_password_button.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reset-password/<int:user_id>/', self.reset_single_password, name='reset-single-password'),
        ]
        return custom_urls + urls

    def reset_single_password(self, request, user_id):
        user = CustomUser.objects.get(id=user_id)
        new_password = '1111'
        user.password = make_password(new_password)
        user.pw_back = new_password  # 실제 비밀번호 값을 저장
        user.save()
        messages.success(request, f"사용자 '{user.username}'의 비밀번호가 '1111'로 초기화되었습니다.")
        return HttpResponseRedirect("../")

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer_phone', 'car_number', 'car_model', 'fuel_type', 'group', 'total_fuel_amount', 'monthly_fuel_amount', 'last_fuel_amount', 'total_fuel_cost', 'monthly_fuel_cost', 'last_fuel_cost', 'created_at', 'station_list')
    list_filter = ('fuel_type', 'group', 'created_at')
    search_fields = ('name', 'customer_phone', 'car_number', 'car_model', 'group')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('기본 정보', {'fields': ('user', 'name', 'customer_phone')}),
        ('차량 정보', {'fields': ('car_number', 'car_model', 'fuel_type')}),
        ('멤버십 정보', {'fields': ('membership_card',)}),
        ('고객 그룹', {'fields': ('group',)}),
        ('주유량 정보', {
            'fields': ('total_fuel_amount', 'monthly_fuel_amount', 'last_fuel_amount', 'last_fuel_date'),
            'classes': ('collapse',)
        }),
        ('날짜 정보', {'fields': ('created_at', 'updated_at')}),
    )

    def station_list(self, obj):
        # 연결된 주유소 목록을 문자열로 반환
        relations = obj.user.station_relations.select_related('station__station_profile').filter(is_active=True)
        if not relations.exists():
            return '-'
        return ', '.join([
            f"{rel.station.station_profile.station_name}({rel.station.station_profile.business_number})" if hasattr(rel.station, 'station_profile') else rel.station.username
            for rel in relations
        ])
    station_list.short_description = '연결 주유소'

@admin.register(StationProfile)
class StationProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'station_name', 'address', 'phone', 'business_number',
                   'oil_company_code', 'agency_code', 'tid']
    search_fields = ['station_name', 'business_number', 'address']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_stations', 'reject_stations']
    
    fieldsets = (
        ('사용자 정보', {'fields': ('user',)}),
        ('주유소 기본 정보', {
            'fields': ('station_name', 'address', 'phone', 'business_number', 'tid')
        }),
        ('주유소 코드 정보', {
            'fields': ('oil_company_code', 'agency_code')
        }),
        ('날짜 정보', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    def approve_stations(self, request, queryset):
        """선택된 주유소들을 승인"""
        from django.utils import timezone
        updated = queryset.update(is_approved=True, approved_at=timezone.now())
        self.message_user(request, f'{updated}개의 주유소가 승인되었습니다.')
    approve_stations.short_description = "선택된 주유소 승인"
    
    def reject_stations(self, request, queryset):
        """선택된 주유소들의 승인을 거절"""
        updated = queryset.update(is_approved=False, approved_at=None)
        self.message_user(request, f'{updated}개의 주유소 승인이 거절되었습니다.')
    reject_stations.short_description = "선택된 주유소 승인 거절"

@admin.register(CustomerUser)
class CustomerUserAdmin(CustomUserAdmin):
    list_display = CustomUserAdmin.list_display + ('station_list', 'coupon_status')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user_type='CUSTOMER')

    def station_list(self, obj):
        # CustomerProfile이 있으면 연결 주유소 목록 반환
        if hasattr(obj, 'customer_profile'):
            relations = obj.station_relations.select_related('station__station_profile').filter(is_active=True)
            if not relations.exists():
                return '-'
            return ', '.join([
                f"{rel.station.station_profile.station_name}({rel.station.station_profile.business_number})" if hasattr(rel.station, 'station_profile') else rel.station.username
                for rel in relations
            ])
        return '-'
    station_list.short_description = '연결 주유소'

    def coupon_status(self, obj):
        """고객의 쿠폰 상태를 표시"""
        # CustomerCoupon 모델을 통해 쿠폰 수를 가져옴
        coupons = CustomerCoupon.objects.filter(customer=obj)
        available = coupons.filter(status='AVAILABLE').count()
        used = coupons.filter(status='USED').count()
        expired = coupons.filter(status='EXPIRED').count()
        
        if available > 0:
            return format_html(
                '<span style="color: #28a745;">사용가능: {}</span> / '
                '<span style="color: #6c757d;">사용완료: {}</span> / '
                '<span style="color: #dc3545;">만료: {}</span>',
                available, used, expired
            )
        elif used > 0 or expired > 0:
            return format_html(
                '<span style="color: #6c757d;">사용완료: {}</span> / '
                '<span style="color: #dc3545;">만료: {}</span>',
                used, expired
            )
        else:
            return '-'
    coupon_status.short_description = '쿠폰 현황'

@admin.register(StationUser)
class StationUserAdmin(CustomUserAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user_type='STATION')

@admin.register(CustomerStationRelation)
class CustomerStationRelationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'station', 'is_primary', 'is_active', 'points', 'created_at']
    list_filter = ['is_primary', 'is_active', 'created_at']
    search_fields = ['customer__username', 'station__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('customer', 'station', 'is_primary', 'is_active')
        }),
        ('포인트 정보', {
            'fields': ('points',)
        }),
        ('날짜 정보', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    actions = ['record_visit', 'set_as_primary', 'unset_primary']
    
    def record_visit(self, request, queryset):
        """선택된 관계에 대해 방문 기록"""
        for relation in queryset:
            relation.record_visit()
        self.message_user(request, f'{queryset.count()}개의 방문이 기록되었습니다.')
    record_visit.short_description = "방문 기록"
    
    def set_as_primary(self, request, queryset):
        """선택된 관계를 주 거래처로 설정"""
        for relation in queryset:
            relation.is_primary = True
            relation.save()
        self.message_user(request, f'{queryset.count()}개의 관계가 주 거래처로 설정되었습니다.')
    set_as_primary.short_description = "주 거래처로 설정"
    
    def unset_primary(self, request, queryset):
        """선택된 관계의 주 거래처 설정을 해제"""
        updated = queryset.update(is_primary=False)
        self.message_user(request, f'{updated}개의 관계가 주 거래처에서 해제되었습니다.')
    unset_primary.short_description = "주 거래처 해제"

# 어드민 사이트 커스터마이징
admin.site.site_header = "Oil Note 관리자"
admin.site.site_title = "Oil Note Admin"
admin.site.index_title = "Oil Note 관리 시스템"
