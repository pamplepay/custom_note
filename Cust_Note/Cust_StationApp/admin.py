from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.contrib import messages
from .models import PointCard, StationCardMapping, StationList
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
        # TID가 있는 카드 매핑만 조회
        cards = StationCardMapping.objects.filter(
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
    list_display = ('number', 'is_used', 'status_display', 'tid_display', 'created_at')
    list_filter = ('is_used', 'created_at')
    search_fields = ('number', 'tid')
    readonly_fields = ('created_at',)
    list_per_page = 50
    actions = ['mark_as_used', 'mark_as_unused', 'bulk_delete_unused']
    
    fieldsets = (
        ('카드 정보', {
            'fields': ('number', 'is_used', 'tid', 'created_at')
        }),
    )
    
    def tid_display(self, obj):
        """TID 정보를 표시"""
        return obj.tid or '미설정'
    tid_display.short_description = 'TID'
    
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
