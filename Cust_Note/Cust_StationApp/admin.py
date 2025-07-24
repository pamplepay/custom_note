from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.contrib import messages
from .models import PointCard, StationCardMapping, StationList, ExcelSalesData, SalesStatistics, MonthlySalesStatistics, Group, PhoneCardMapping, CouponType, CouponTemplate, CustomerCoupon
from Cust_User.models import CustomUser

class StationCardMappingInline(admin.TabularInline):
    model = StationCardMapping
    extra = 0
    fields = ('card', 'is_active', 'registered_at')
    readonly_fields = ('registered_at',)
    can_delete = True
    verbose_name = '포인트카드'
    verbose_name_plural = '포인트카드 목록'

@admin.register(StationList)
class StationListAdmin(admin.ModelAdmin):
    change_list_template = 'admin/station_list_change_list.html'
    change_form_template = 'admin/station_detail.html'
    list_display = ('username', 'get_station_name_link', 'card_count', 'view_station_detail')
    list_filter = ('is_active',)
    search_fields = ('username', 'station_profile__station_name')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:station_id>/cards/',
                self.admin_site.admin_view(self.station_cards_view),
                name='station-cards',
            ),
            path(
                '<int:station_id>/cards/action/',
                self.admin_site.admin_view(self.station_cards_action),
                name='station-cards-action',
            ),
        ]
        return custom_urls + urls
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            user_type='STATION'
        ).select_related('station_profile')
    
    def get_station_name_link(self, obj):
        url = reverse('admin:station-cards', args=[obj.id])
        station_name = obj.station_profile.station_name if hasattr(obj, 'station_profile') else '-'
        return format_html(
            '<a href="{}" style="color: #417690; text-decoration: none;">'
            '<strong>{}</strong></a>',
            url, station_name
        )
    get_station_name_link.short_description = '주유소명'
    get_station_name_link.admin_order_field = 'station_profile__station_name'
    
    def card_count(self, obj):
        # TID가 있는 카드 매핑 수를 반환
        count = StationCardMapping.objects.filter(tid__isnull=False).count()
        return f'{count}장'
    card_count.short_description = '등록 카드 수'
    
    def view_station_detail(self, obj):
        url = reverse('admin:station-cards', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" '
            'style="background-color: #7FB3D5; color: white; '
            'padding: 5px 10px; border-radius: 4px; text-decoration: none;">'
            '<i class="fas fa-credit-card"></i> 카드 관리</a>',
            url
        )
    view_station_detail.short_description = '카드 관리'
    
    def station_cards_view(self, request, station_id):
        station = get_object_or_404(CustomUser, id=station_id, user_type='STATION')
        # 해당 주유소의 TID가 있는 카드 매핑만 조회
        cards = StationCardMapping.objects.filter(
            station=station,
            tid__isnull=False
        ).select_related('card').order_by('-registered_at')
        
        # 통계 정보 계산
        total_cards = cards.count()
        active_cards = cards.filter(is_active=True).count()
        inactive_cards = total_cards - active_cards
        
        active_percentage = (active_cards / total_cards * 100) if total_cards > 0 else 0
        inactive_percentage = (inactive_cards / total_cards * 100) if total_cards > 0 else 0
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'{station.station_profile.station_name} 포인트카드 목록',
            'station': station,
            'cards': cards,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request, station),
            # 통계 정보 추가
            'total_cards': total_cards,
            'active_cards': active_cards,
            'inactive_cards': inactive_cards,
            'active_percentage': active_percentage,
            'inactive_percentage': inactive_percentage,
        }
        
        return TemplateResponse(
            request,
            'admin/station_cards.html',
            context,
        )
    
    def station_cards_action(self, request, station_id):
        if request.method != 'POST':
            return redirect('admin:station-cards', station_id=station_id)
        
        if 'action' not in request.POST or request.POST['action'] != 'delete_selected':
            messages.error(request, '유효하지 않은 작업입니다.')
            return redirect('admin:station-cards', station_id=station_id)
        
        selected = request.POST.getlist('_selected_action')
        if not selected:
            messages.warning(request, '선택된 카드가 없습니다.')
            return redirect('admin:station-cards', station_id=station_id)
        
        try:
            # 선택된 카드 매핑 삭제
            StationCardMapping.objects.filter(
                id__in=selected,
                station_id=station_id
            ).delete()
            
            messages.success(request, f'{len(selected)}개의 카드가 삭제되었습니다.')
        except Exception as e:
            messages.error(request, f'카드 삭제 중 오류가 발생했습니다: {str(e)}')
        
        return redirect('admin:station-cards', station_id=station_id)

@admin.register(PointCard)
class PointCardAdmin(admin.ModelAdmin):
    list_display = ('number', 'is_used', 'status_display', 'user_info', 'registered_station_info', 'station_info', 'mappings_display')
    list_filter = ('is_used', 'created_at', 'mappings__station__station_profile__station_name')
    search_fields = ('number', 'tids', 'mappings__station__station_profile__station_name')
    readonly_fields = ('created_at', 'tids', 'mappings_display', 'user_info', 'registered_station_info', 'station_info')
    list_per_page = 50
    actions = ['mark_as_used', 'mark_as_unused', 'bulk_delete_unused']
    
    fieldsets = (
        ('카드 정보', {
            'fields': ('number', 'is_used', 'tids', 'created_at')
        }),
        ('등록 주유소', {
            'fields': ('registered_station_info',)
        }),
        ('소유 주유소', {
            'fields': ('station_info',)
        }),
        ('사용자 정보', {
            'fields': ('user_info',)
        }),
        ('매핑 정보', {
            'fields': ('mappings_display',)
        }),
    )
    
    def tids_display(self, obj):
        """TID 목록을 표시"""
        if not obj.tids:
            return format_html('<span style="color: #95a5a6;">미등록</span>')
        return format_html('<br>'.join(obj.tids))
    tids_display.short_description = 'TID 목록'
    
    def mappings_display(self, obj):
        """매핑 정보를 상세히 표시"""
        mappings = obj.mappings.all()
        if not mappings:
            return format_html('<span style="color: #95a5a6;">등록된 매핑 없음</span>')
        
        html = ['<table style="width: 100%; border-collapse: collapse;">']
        html.append('<tr style="background-color: #f5f6fa;">')
        html.append('<th style="padding: 8px; border: 1px solid #ddd;">TID</th>')
        html.append('<th style="padding: 8px; border: 1px solid #ddd;">상태</th>')
        html.append('<th style="padding: 8px; border: 1px solid #ddd;">등록일</th>')
        html.append('</tr>')
        
        for mapping in mappings:
            status_color = '#27ae60' if mapping.is_active else '#e74c3c'
            status_text = '활성' if mapping.is_active else '비활성'
            html.append('<tr>')
            html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">{mapping.tid or "-"}</td>')
            html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">'
                       f'<span style="color: {status_color};">●</span> {status_text}</td>')
            html.append(f'<td style="padding: 8px; border: 1px solid #ddd;">'
                       f'{mapping.registered_at.strftime("%Y-%m-%d %H:%M")}</td>')
            html.append('</tr>')
        
        html.append('</table>')
        return format_html(''.join(html))
    mappings_display.short_description = '매핑 정보'
    
    def status_display(self, obj):
        """사용 상태를 시각적으로 표시"""
        if obj.is_used:
            return format_html(
                '<span style="color: #e74c3c; font-weight: bold;">●</span> 사용중'
            )
        else:
            return format_html(
                '<span style="color: #27ae60; font-weight: bold;">●</span> 미사용'
            )
    status_display.short_description = '상태'
    
    def user_info(self, obj):
        """카드를 사용 중인 사용자 정보를 표시"""
        if not obj.is_used:
            return format_html('<span style="color: #95a5a6;">미사용</span>')
        
        # PhoneCardMapping에서 이 카드를 사용 중인 사용자 찾기
        phone_mappings = PhoneCardMapping.objects.filter(
            membership_card=obj,
            is_used=True
        ).select_related('linked_user', 'station', 'station__station_profile')
        
        if not phone_mappings.exists():
            return format_html('<span style="color: #f39c12;">사용중 (연동 정보 없음)</span>')
        
        user_info_list = []
        for mapping in phone_mappings:
            # 주유소 정보 가져오기
            station = mapping.station
            if station is None:
                station_info = '<span style="color: #e74c3c;">주유소 정보 없음 (삭제됨)</span>'
            elif hasattr(station, 'station_profile'):
                station_name = station.station_profile.station_name
                station_address = station.station_profile.address
                station_phone = station.station_profile.phone
                station_info = f"{station_name}<br><small style='color: #7f8c8d;'>{station_address} | {station_phone}</small>"
            else:
                station_info = station.username
            
            if mapping.linked_user:
                # 연동된 사용자가 있는 경우
                user = mapping.linked_user
                user_info_list.append(
                    f'<div style="margin-bottom: 8px;">'
                    f'<span style="color: #27ae60; font-weight: bold;">{user.username}</span><br>'
                    f'<span style="color: #3498db; font-weight: bold;">주유소:</span> {station_info}<br>'
                    f'<small style="color: #95a5a6;">연동일: {mapping.created_at.strftime("%Y-%m-%d %H:%M")}</small>'
                    f'</div>'
                )
            else:
                # 연동되지 않은 폰번호-카드 매핑
                user_info_list.append(
                    f'<div style="margin-bottom: 8px;">'
                    f'<span style="color: #e67e22; font-weight: bold;">{mapping.phone_number}</span><br>'
                    f'<span style="color: #3498db; font-weight: bold;">주유소:</span> {station_info}<br>'
                    f'<small style="color: #95a5a6;">등록일: {mapping.created_at.strftime("%Y-%m-%d %H:%M")}</small>'
                    f'</div>'
                )
        
        return format_html(''.join(user_info_list))
    
    user_info.short_description = '사용자 정보'
    
    def registered_station_info(self, obj):
        """카드가 등록된 주유소 정보를 표시 (PhoneCardMapping 기준)"""
        # PhoneCardMapping에서 이 카드가 등록된 주유소들 찾기
        phone_mappings = PhoneCardMapping.objects.filter(
            membership_card=obj
        ).select_related('station', 'station__station_profile')
        
        if not phone_mappings.exists():
            return format_html('<span style="color: #95a5a6;">등록된 주유소 없음</span>')
        
        station_list = []
        for mapping in phone_mappings:
            station = mapping.station
            if station is None:
                status_color = '#e74c3c' if mapping.is_used else '#95a5a6'
                status_text = '사용중' if mapping.is_used else '미사용'
                station_list.append(
                    f'<div style="margin-bottom: 4px;">'
                    f'<span style="color: #e74c3c; font-weight: bold;">주유소 정보 없음</span><br>'
                    f'<small style="color: #95a5a6;">매핑된 주유소가 삭제됨</small><br>'
                    f'<small style="color: {status_color};">{status_text}</small>'
                    f'</div>'
                )
            elif hasattr(station, 'station_profile'):
                station_name = station.station_profile.station_name
                station_address = station.station_profile.address
                status_color = '#27ae60' if mapping.is_used else '#95a5a6'
                status_text = '사용중' if mapping.is_used else '미사용'
                station_list.append(
                    f'<div style="margin-bottom: 4px;">'
                    f'<span style="color: #3498db; font-weight: bold;">{station_name}</span><br>'
                    f'<small style="color: #7f8c8d;">{station_address}</small><br>'
                    f'<small style="color: {status_color};">{status_text}</small>'
                    f'</div>'
                )
            else:
                status_color = '#27ae60' if mapping.is_used else '#95a5a6'
                status_text = '사용중' if mapping.is_used else '미사용'
                station_list.append(
                    f'<div style="margin-bottom: 4px;">'
                    f'<span style="color: #3498db; font-weight: bold;">{station.username}</span><br>'
                    f'<small style="color: #95a5a6;">프로필 정보 없음</small><br>'
                    f'<small style="color: {status_color};">{status_text}</small>'
                    f'</div>'
                )
        
        return format_html(''.join(station_list))
    
    registered_station_info.short_description = '등록 주유소'
    
    def station_info(self, obj):
        """카드의 소유 주유소 정보를 표시 (TID 매핑 기준)"""
        # StationCardMapping에서 이 카드의 소유 주유소 찾기
        station_mappings = StationCardMapping.objects.filter(
            card=obj,
            is_active=True
        ).select_related('station', 'station__station_profile')
        
        if not station_mappings.exists():
            return format_html('<span style="color: #95a5a6;">소유 주유소 없음</span>')
        
        station_list = []
        for mapping in station_mappings:
            station = mapping.station
            if station is None:
                tid_info = f"TID: {mapping.tid}" if mapping.tid else "TID: 미등록"
                station_list.append(
                    f'<div style="margin-bottom: 4px;">'
                    f'<span style="color: #e74c3c; font-weight: bold;">주유소 정보 없음</span><br>'
                    f'<small style="color: #95a5a6;">매핑된 주유소가 삭제됨</small><br>'
                    f'<small style="color: #e67e22; font-weight: bold;">{tid_info}</small>'
                    f'</div>'
                )
            elif hasattr(station, 'station_profile'):
                station_name = station.station_profile.station_name
                station_address = station.station_profile.address
                station_phone = station.station_profile.phone
                tid_info = f"TID: {mapping.tid}" if mapping.tid else "TID: 미등록"
                station_list.append(
                    f'<div style="margin-bottom: 4px;">'
                    f'<span style="color: #3498db; font-weight: bold;">{station_name}</span><br>'
                    f'<small style="color: #7f8c8d;">{station_address}</small><br>'
                    f'<small style="color: #7f8c8d;">{station_phone}</small><br>'
                    f'<small style="color: #e67e22; font-weight: bold;">{tid_info}</small>'
                    f'</div>'
                )
            else:
                tid_info = f"TID: {mapping.tid}" if mapping.tid else "TID: 미등록"
                station_list.append(
                    f'<div style="margin-bottom: 4px;">'
                    f'<span style="color: #3498db; font-weight: bold;">{station.username}</span><br>'
                    f'<small style="color: #95a5a6;">프로필 정보 없음</small><br>'
                    f'<small style="color: #e67e22; font-weight: bold;">{tid_info}</small>'
                    f'</div>'
                )
        
        return format_html(''.join(station_list))
    
    station_info.short_description = '소유 주유소'
    
    def mark_as_used(self, request, queryset):
        """선택된 카드들을 사용중으로 표시"""
        updated = queryset.update(is_used=True)
        self.message_user(request, f'{updated}개의 카드가 사용중으로 표시되었습니다.')
    mark_as_used.short_description = "선택된 카드를 사용중으로 표시"
    
    def mark_as_unused(self, request, queryset):
        """선택된 카드들을 미사용으로 표시"""
        updated = queryset.update(is_used=False)
        self.message_user(request, f'{updated}개의 카드가 미사용으로 표시되었습니다.')
    mark_as_unused.short_description = "선택된 카드를 미사용으로 표시"
    
    def bulk_delete_unused(self, request, queryset):
        """선택된 미사용 카드들을 삭제"""
        unused_cards = queryset.filter(is_used=False)
        count = unused_cards.count()
        unused_cards.delete()
        self.message_user(request, f'{count}개의 미사용 카드가 삭제되었습니다.')
    bulk_delete_unused.short_description = "선택된 미사용 카드 삭제"

@admin.register(SalesStatistics)
class SalesStatisticsAdmin(admin.ModelAdmin):
    change_list_template = 'admin/sales_statistics_change_list.html'
    list_display = ('tid', 'get_station_name', 'sale_date', 'total_transactions', 'total_amount', 'avg_unit_price', 'top_product', 'source_file', 'created_at')
    list_filter = ('sale_date', 'source_file', 'created_at')
    search_fields = ('tid', 'top_product', 'source_file')
    readonly_fields = ('created_at',)
    list_per_page = 50
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('tid', 'sale_date', 'source_file', 'created_at')
        }),
        ('통계 정보', {
            'fields': ('total_transactions', 'total_quantity', 'total_amount', 'avg_unit_price')
        }),
        ('제품 정보', {
            'fields': ('top_product', 'top_product_count')
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'station-filter/',
                self.admin_site.admin_view(self.station_filter_view),
                name='sales-statistics-station-filter',
            ),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        """주유소 목록을 템플릿에 전달"""
        from Cust_User.models import StationProfile
        
        # 모든 주유소 프로필 가져오기 (TID가 있는 것만)
        stations = StationProfile.objects.filter(
            tid__isnull=False
        ).exclude(tid='').select_related('user').order_by('station_name')
        
        extra_context = extra_context or {}
        extra_context['stations'] = stations
        
        return super().changelist_view(request, extra_context)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).order_by('-sale_date', '-created_at')
        
        # 주유소 필터 적용
        station_filter = request.GET.get('station_filter')
        if station_filter and station_filter != 'all':
            # TID로 주유소 찾기
            from Cust_User.models import StationProfile
            station_profiles = StationProfile.objects.filter(tid=station_filter)
            if station_profiles.exists():
                queryset = queryset.filter(tid=station_filter)
        
        return queryset
    
    def get_search_results(self, request, queryset, search_term):
        """검색 기능 개선 - 주유소명으로도 검색 가능"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            from Cust_User.models import StationProfile
            
            # 주유소명으로 검색
            station_profiles = StationProfile.objects.filter(
                station_name__icontains=search_term,
                tid__isnull=False
            ).exclude(tid='')
            
            if station_profiles.exists():
                station_tids = [profile.tid for profile in station_profiles]
                queryset |= self.model.objects.filter(tid__in=station_tids)
        
        return queryset, use_distinct

    def get_station_name(self, obj):
        """TID로 주유소명 가져오기"""
        if obj.tid:
            from Cust_User.models import StationProfile
            try:
                station_profile = StationProfile.objects.get(tid=obj.tid)
                return station_profile.station_name
            except StationProfile.DoesNotExist:
                return f"TID: {obj.tid} (주유소 정보 없음)"
        return "-"
    get_station_name.short_description = '주유소명'
    get_station_name.admin_order_field = 'tid'
    
    def station_filter_view(self, request):
        """주유소 필터 뷰"""
        from Cust_User.models import StationProfile
        
        # 모든 주유소 프로필 가져오기 (TID가 있는 것만)
        stations = StationProfile.objects.filter(
            tid__isnull=False
        ).exclude(tid='').select_related('user').order_by('station_name')
        
        # 현재 선택된 주유소
        selected_station = request.GET.get('station_filter', 'all')
        
        # 필터링된 데이터
        if selected_station and selected_station != 'all':
            queryset = self.get_queryset(request).filter(tid=selected_station)
        else:
            queryset = self.get_queryset(request)
        
        context = {
            **self.admin_site.each_context(request),
            'title': '매출 통계 - 주유소별 필터',
            'stations': stations,
            'selected_station': selected_station,
            'queryset': queryset,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
        }
        
        return TemplateResponse(
            request,
            'admin/sales_statistics_station_filter.html',
            context,
        )

@admin.register(ExcelSalesData)
class ExcelSalesDataAdmin(admin.ModelAdmin):
    change_list_template = 'admin/excel_sales_data_change_list.html'
    list_display = ('tid', 'get_station_name', 'sale_date', 'sale_time', 'customer_name', 'product_pack', 'quantity', 'total_amount', 'source_file')
    list_filter = ('sale_date', 'product_pack', 'tid', 'source_file')
    search_fields = ('customer_name', 'product_pack', 'tid', 'source_file')
    readonly_fields = ('data_created_at',)
    list_per_page = 50
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('tid', 'sale_date', 'sale_time', 'source_file')
        }),
        ('고객 정보', {
            'fields': ('customer_number', 'customer_name', 'issue_number')
        }),
        ('제품 정보', {
            'fields': ('product_type', 'product_code', 'product_pack', 'nozzle')
        }),
        ('판매 정보', {
            'fields': ('sale_type', 'payment_type', 'sale_type2', 'quantity', 'unit_price', 'total_amount')
        }),
        ('포인트 정보', {
            'fields': ('earned_points', 'points', 'bonus')
        }),
        ('시스템 정보', {
            'fields': ('pos_id', 'pos_code', 'store', 'receipt', 'approval_number', 'approval_datetime', 'bonus_card', 'customer_card_number', 'data_created_at')
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'station-filter/',
                self.admin_site.admin_view(self.station_filter_view),
                name='excel-sales-data-station-filter',
            ),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        """주유소 목록을 템플릿에 전달"""
        from Cust_User.models import StationProfile
        
        # 모든 주유소 프로필 가져오기 (TID가 있는 것만)
        stations = StationProfile.objects.filter(
            tid__isnull=False
        ).exclude(tid='').select_related('user').order_by('station_name')
        
        extra_context = extra_context or {}
        extra_context['stations'] = stations
        
        return super().changelist_view(request, extra_context)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).order_by('-sale_date', '-sale_time')
        
        # 주유소 필터 적용
        station_filter = request.GET.get('station_filter')
        if station_filter and station_filter != 'all':
            queryset = queryset.filter(tid=station_filter)
        
        return queryset
    
    def get_search_results(self, request, queryset, search_term):
        """검색 기능 개선 - 주유소명으로도 검색 가능"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            from Cust_User.models import StationProfile
            
            # 주유소명으로 검색
            station_profiles = StationProfile.objects.filter(
                station_name__icontains=search_term,
                tid__isnull=False
            ).exclude(tid='')
            
            if station_profiles.exists():
                station_tids = [profile.tid for profile in station_profiles]
                queryset |= self.model.objects.filter(tid__in=station_tids)
        
        return queryset, use_distinct
    
    def get_station_name(self, obj):
        """TID로 주유소명 가져오기"""
        if obj.tid:
            from Cust_User.models import StationProfile
            try:
                station_profile = StationProfile.objects.get(tid=obj.tid)
                return station_profile.station_name
            except StationProfile.DoesNotExist:
                return f"TID: {obj.tid} (주유소 정보 없음)"
        return "-"
    get_station_name.short_description = '주유소명'
    get_station_name.admin_order_field = 'tid'
    
    def station_filter_view(self, request):
        """주유소 필터 뷰"""
        from Cust_User.models import StationProfile
        
        # 모든 주유소 프로필 가져오기 (TID가 있는 것만)
        stations = StationProfile.objects.filter(
            tid__isnull=False
        ).exclude(tid='').select_related('user').order_by('station_name')
        
        # 현재 선택된 주유소
        selected_station = request.GET.get('station_filter', 'all')
        
        # 필터링된 데이터
        if selected_station and selected_station != 'all':
            queryset = self.get_queryset(request).filter(tid=selected_station)
        else:
            queryset = self.get_queryset(request)
        
        context = {
            **self.admin_site.each_context(request),
            'title': '엑셀 매출 데이터 - 주유소별 필터',
            'stations': stations,
            'selected_station': selected_station,
            'queryset': queryset,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
        }
        
        return TemplateResponse(
            request,
            'admin/excel_sales_data_station_filter.html',
            context,
        )


@admin.register(MonthlySalesStatistics)
class MonthlySalesStatisticsAdmin(admin.ModelAdmin):
    change_list_template = 'admin/monthly_sales_statistics_change_list.html'
    list_display = ('tid', 'get_station_name', 'year_month', 'total_transactions', 'total_amount', 'avg_unit_price', 'top_product', 'updated_at')
    list_filter = ('year_month', 'tid', 'updated_at')
    search_fields = ('tid', 'top_product', 'year_month')
    readonly_fields = ('updated_at',)
    list_per_page = 50
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('tid', 'year_month', 'updated_at')
        }),
        ('통계 정보', {
            'fields': ('total_transactions', 'total_quantity', 'total_amount', 'avg_unit_price')
        }),
        ('제품 정보', {
            'fields': ('top_product', 'top_product_count')
        }),
        ('유종별 판매 현황', {
            'fields': ('product_breakdown',)
        }),
        ('제품별 상세 누적 데이터', {
            'fields': ('product_sales_count', 'product_sales_quantity', 'product_sales_amount')
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'station-filter/',
                self.admin_site.admin_view(self.station_filter_view),
                name='monthly-sales-statistics-station-filter',
            ),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        """주유소 목록을 템플릿에 전달"""
        from Cust_User.models import StationProfile
        
        # 모든 주유소 프로필 가져오기 (TID가 있는 것만)
        stations = StationProfile.objects.filter(
            tid__isnull=False
        ).exclude(tid='').select_related('user').order_by('station_name')
        
        extra_context = extra_context or {}
        extra_context['stations'] = stations
        
        return super().changelist_view(request, extra_context)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request).order_by('-year_month', '-updated_at')
        
        # 주유소 필터 적용
        station_filter = request.GET.get('station_filter')
        if station_filter and station_filter != 'all':
            queryset = queryset.filter(tid=station_filter)
        
        return queryset
    
    def get_search_results(self, request, queryset, search_term):
        """검색 기능 개선 - 주유소명으로도 검색 가능"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            from Cust_User.models import StationProfile
            
            # 주유소명으로 검색
            station_profiles = StationProfile.objects.filter(
                station_name__icontains=search_term,
                tid__isnull=False
            ).exclude(tid='')
            
            if station_profiles.exists():
                station_tids = [profile.tid for profile in station_profiles]
                queryset |= self.model.objects.filter(tid__in=station_tids)
        
        return queryset, use_distinct
    
    def get_station_name(self, obj):
        """TID로 주유소명 가져오기"""
        if obj.tid:
            from Cust_User.models import StationProfile
            try:
                station_profile = StationProfile.objects.get(tid=obj.tid)
                return station_profile.station_name
            except StationProfile.DoesNotExist:
                return f"TID: {obj.tid} (주유소 정보 없음)"
        return "-"
    get_station_name.short_description = '주유소명'
    get_station_name.admin_order_field = 'tid'
    
    def station_filter_view(self, request):
        """주유소 필터 뷰"""
        from Cust_User.models import StationProfile
        
        # 모든 주유소 프로필 가져오기 (TID가 있는 것만)
        stations = StationProfile.objects.filter(
            tid__isnull=False
        ).exclude(tid='').select_related('user').order_by('station_name')
        
        # 현재 선택된 주유소
        selected_station = request.GET.get('station_filter', 'all')
        
        # 필터링된 데이터
        if selected_station and selected_station != 'all':
            queryset = self.get_queryset(request).filter(tid=selected_station)
        else:
            queryset = self.get_queryset(request)
        
        context = {
            **self.admin_site.each_context(request),
            'title': '월별 매출 통계 - 주유소별 필터',
            'stations': stations,
            'selected_station': selected_station,
            'queryset': queryset,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
        }
        
        return TemplateResponse(
            request,
            'admin/monthly_sales_statistics_station_filter.html',
            context,
        )

@admin.register(StationCardMapping)
class StationCardMappingAdmin(admin.ModelAdmin):
    list_display = ('card', 'tid', 'is_active', 'registered_at')
    list_filter = ('is_active', 'registered_at')
    search_fields = ('card__number', 'tid')
    readonly_fields = ('registered_at',)
    raw_id_fields = ('card',)
    
    fieldsets = (
        ('매핑 정보', {
            'fields': ('card', 'tid', 'is_active', 'registered_at')
        }),
    )

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'station', 'customer_count', 'created_at')
    list_filter = ('created_at', 'station')
    search_fields = ('name', 'station__username', 'station__station_profile__station_name')
    readonly_fields = ('created_at', 'customer_count')
    list_per_page = 50
    
    fieldsets = (
        ('그룹 정보', {
            'fields': ('name', 'station', 'created_at')
        }),
        ('고객 현황', {
            'fields': ('customer_count',)
        }),
    )
    
    def customer_count(self, obj):
        """이 그룹에 속한 고객 수 반환"""
        count = obj.get_customer_count()
        return format_html(
            '<span style="color: #2980b9; font-weight: bold;">{}</span>명',
            count
        )
    customer_count.short_description = '고객 수'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('station', 'station__station_profile')

@admin.register(PhoneCardMapping)
class PhoneCardMappingAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'membership_card', 'station', 'car_number_display', 'is_used', 'linked_user', 'created_at')
    list_filter = ('is_used', 'created_at', 'station')
    search_fields = ('phone_number', 'membership_card__number', 'station__username', 'linked_user__username', 'car_number')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('membership_card', 'station', 'linked_user')
    list_per_page = 50
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('phone_number', 'membership_card', 'station')
        }),
        ('고객 정보', {
            'fields': ('car_number',)
        }),
        ('연동 정보', {
            'fields': ('is_used', 'linked_user')
        }),
        ('시간 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'membership_card', 'station', 'linked_user'
        )
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_used:  # 이미 연동된 경우
            return self.readonly_fields + ('phone_number', 'membership_card', 'station')
        return self.readonly_fields
    
    def car_number_display(self, obj):
        """차량번호 표시 (비어있으면 '-' 표시)"""
        return obj.car_number if obj.car_number else '-'
    car_number_display.short_description = '차량번호'
    car_number_display.admin_order_field = 'car_number'
    
    actions = ['unlink_users', 'bulk_delete_unused']
    
    def unlink_users(self, request, queryset):
        """선택된 연동 정보에서 사용자 연동 해제"""
        count = 0
        for mapping in queryset.filter(is_used=True):
            mapping.unlink_user()
            count += 1
        
        if count > 0:
            self.message_user(request, f'{count}개의 연동 정보에서 사용자 연동이 해제되었습니다.')
        else:
            self.message_user(request, '연동 해제할 항목이 없습니다.')
    unlink_users.short_description = '사용자 연동 해제'
    
    def bulk_delete_unused(self, request, queryset):
        """미사용 연동 정보 일괄 삭제"""
        unused_mappings = queryset.filter(is_used=False)
        count = unused_mappings.count()
        unused_mappings.delete()
        
        self.message_user(request, f'{count}개의 미사용 연동 정보가 삭제되었습니다.')
    bulk_delete_unused.short_description = '미사용 연동 정보 일괄 삭제'

@admin.register(CouponType)
class CouponTypeAdmin(admin.ModelAdmin):
    list_display = ('station', 'type_name', 'type_code', 'is_default', 'is_active', 'created_at')
    list_filter = ('is_default', 'is_active', 'created_at')
    search_fields = ('type_name', 'type_code', 'station__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('station', 'type_code', 'type_name')
        }),
        ('설정', {
            'fields': ('is_default', 'is_active', 'created_at')
        }),
    )

@admin.register(CouponTemplate)
class CouponTemplateAdmin(admin.ModelAdmin):
    list_display = ('station', 'coupon_name', 'coupon_type', 'benefit_type', 'discount_amount', 'product_name', 'is_active', 'created_at')
    list_filter = ('benefit_type', 'is_active', 'is_permanent', 'created_at', 'coupon_type')
    search_fields = ('coupon_name', 'description', 'station__username', 'product_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('station', 'coupon_type', 'coupon_name', 'description')
        }),
        ('혜택 설정', {
            'fields': ('benefit_type', 'discount_amount', 'product_name')
        }),
        ('유효기간', {
            'fields': ('is_permanent', 'valid_from', 'valid_until')
        }),
        ('관리', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(CustomerCoupon)
class CustomerCouponAdmin(admin.ModelAdmin):
    list_display = ('customer', 'coupon_template', 'status_display', 'issued_date', 'used_date', 'expiry_date')
    list_filter = ('status', 'issued_date', 'used_date', 'expiry_date', 'coupon_template__station')
    search_fields = ('customer__username', 'customer__phone_number', 'coupon_template__coupon_name', 'coupon_template__station__username')
    readonly_fields = ('issued_date', 'used_date', 'status_display')
    list_per_page = 50
    actions = ['bulk_issue_coupons', 'bulk_delete_unused', 'mark_as_used', 'mark_as_unused']
    
    fieldsets = (
        ('쿠폰 정보', {
            'fields': ('coupon_template', 'status')
        }),
        ('고객 정보', {
            'fields': ('customer',)
        }),
        ('시간 정보', {
            'fields': ('issued_date', 'used_date', 'expiry_date', 'status_display'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'coupon_template', 'coupon_template__station')
    
    def status_display(self, obj):
        """쿠폰 상태 표시"""
        status = obj.get_status_display()
        if status == "사용됨":
            color = "#e74c3c"
        elif status == "발행됨":
            color = "#f39c12"
        else:
            color = "#27ae60"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status
        )
    status_display.short_description = '상태'
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == 'USED':  # 이미 사용된 쿠폰
            return self.readonly_fields + ('coupon_template', 'customer')
        elif obj and obj.issued_date:  # 이미 발행된 쿠폰
            return self.readonly_fields + ('coupon_template',)
        return self.readonly_fields
    
    def bulk_issue_coupons(self, request, queryset):
        """선택된 쿠폰들을 일괄 발행"""
        available_coupons = queryset.filter(status='AVAILABLE')
        count = available_coupons.count()
        
        if count == 0:
            self.message_user(request, '발행할 수 있는 쿠폰이 없습니다.')
            return
        
        # 여기서는 일괄 발행 대신 개별 발행을 안내
        self.message_user(request, f'{count}개의 쿠폰이 선택되었습니다. 개별적으로 고객에게 발행해주세요.')
    bulk_issue_coupons.short_description = '선택된 쿠폰 일괄 발행'
    
    def bulk_delete_unused(self, request, queryset):
        """미사용 쿠폰 일괄 삭제"""
        unused_coupons = queryset.filter(status='AVAILABLE')
        count = unused_coupons.count()
        unused_coupons.delete()
        
        self.message_user(request, f'{count}개의 미사용 쿠폰이 삭제되었습니다.')
    bulk_delete_unused.short_description = '미사용 쿠폰 일괄 삭제'
    
    def mark_as_used(self, request, queryset):
        """선택된 쿠폰들을 사용됨으로 표시"""
        available_coupons = queryset.filter(status='AVAILABLE')
        count = 0
        
        for coupon in available_coupons:
            try:
                coupon.use_coupon()
                count += 1
            except ValueError as e:
                self.message_user(request, f'쿠폰 {coupon.id}: {str(e)}', level=messages.ERROR)
        
        if count > 0:
            self.message_user(request, f'{count}개의 쿠폰이 사용됨으로 표시되었습니다.')
    mark_as_used.short_description = '선택된 쿠폰 사용됨으로 표시'
    
    def mark_as_unused(self, request, queryset):
        """선택된 쿠폰들을 미사용으로 표시 (관리자용)"""
        used_coupons = queryset.filter(status='USED')
        count = 0
        
        for coupon in used_coupons:
            coupon.status = 'AVAILABLE'
            coupon.used_date = None
            coupon.save()
            count += 1
        
        if count > 0:
            self.message_user(request, f'{count}개의 쿠폰이 미사용으로 표시되었습니다.')
    mark_as_unused.short_description = '선택된 쿠폰 미사용으로 표시'
