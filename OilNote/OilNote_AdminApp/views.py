from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json

# from .models import SystemLog, AdminAction, SystemConfig, DataBackup, MaintenanceSchedule
from OilNote_User.models import CustomUser, CustomerProfile, StationProfile
from OilNote_StationApp.models import PointCard, ExcelSalesData, SalesStatistics

def is_admin(user):
    """관리자 권한 확인"""
    return user.is_authenticated and user.is_staff

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """관리자 대시보드"""
    # 기본 통계
    total_users = CustomUser.objects.count()
    total_customers = CustomUser.objects.filter(user_type='CUSTOMER').count()
    total_stations = CustomUser.objects.filter(user_type='STATION').count()
    total_cards = PointCard.objects.count()
    
    # 최근 활동 (임시로 빈 리스트)
    recent_logs = []
    recent_actions = []
    
    # 시스템 상태 (임시로 빈 리스트)
    system_configs = []
    
    # 예정된 유지보수 (임시로 빈 리스트)
    upcoming_maintenance = []
    
    context = {
        'total_users': total_users,
        'total_customers': total_customers,
        'total_stations': total_stations,
        'total_cards': total_cards,
        'recent_logs': recent_logs,
        'recent_actions': recent_actions,
        'system_configs': system_configs,
        'upcoming_maintenance': upcoming_maintenance,
    }
    
    return render(request, 'OilNote_AdminApp/admin_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def system_logs(request):
    """시스템 로그 조회"""
    # 임시로 빈 페이지네이션 객체 생성
    from django.core.paginator import EmptyPage, PageNotAnInteger
    
    class DummyPaginator:
        def __init__(self):
            self.num_pages = 0
            self.page_range = []
        
        def get_page(self, page_number):
            return DummyPage()
    
    class DummyPage:
        def __init__(self):
            self.object_list = []
            self.number = 1
            self.has_previous = False
            self.has_next = False
            self.previous_page_number = None
            self.next_page_number = None
            self.paginator = DummyPaginator()
    
    context = {
        'page_obj': DummyPage(),
        'log_types': [],
        'current_filters': {
            'log_type': request.GET.get('log_type'),
            'search': request.GET.get('search'),
        }
    }
    
    return render(request, 'OilNote_AdminApp/system_logs.html', context)

@login_required
@user_passes_test(is_admin)
def admin_actions(request):
    """관리자 액션 로그 조회"""
    actions = AdminAction.objects.all()
    
    # 필터링
    action_type = request.GET.get('action_type')
    if action_type:
        actions = actions.filter(action_type=action_type)
    
    # 검색
    search = request.GET.get('search')
    if search:
        actions = actions.filter(
            Q(admin_user__username__icontains=search) |
            Q(description__icontains=search) |
            Q(target_model__icontains=search)
        )
    
    # 페이지네이션
    paginator = Paginator(actions, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'action_types': AdminAction.ACTION_TYPES,
        'current_filters': {
            'action_type': action_type,
            'search': search,
        }
    }
    
    return render(request, 'OilNote_AdminApp/admin_actions.html', context)

@login_required
@user_passes_test(is_admin)
def system_config(request):
    """시스템 설정 관리"""
    if request.method == 'POST':
        config_key = request.POST.get('config_key')
        config_value = request.POST.get('config_value')
        config_type = request.POST.get('config_type')
        description = request.POST.get('description')
        is_active = request.POST.get('is_active') == 'on'
        
        config, created = SystemConfig.objects.update_or_create(
            config_key=config_key,
            defaults={
                'config_value': config_value,
                'config_type': config_type,
                'description': description,
                'is_active': is_active,
            }
        )
        
        # 관리자 액션 로그 기록
        AdminAction.objects.create(
            admin_user=request.user,
            action_type='SYSTEM_CONFIG',
            target_model='SystemConfig',
            target_id=config.id,
            description=f'시스템 설정 {"생성" if created else "수정"}: {config_key}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        messages.success(request, f'시스템 설정이 {"생성" if created else "수정"}되었습니다.')
        return redirect('admin_panel:system_config')
    
    configs = SystemConfig.objects.all()
    context = {
        'configs': configs,
        'config_types': SystemConfig.CONFIG_TYPES,
    }
    
    return render(request, 'OilNote_AdminApp/system_config.html', context)

@login_required
@user_passes_test(is_admin)
def data_backup(request):
    """데이터 백업 관리"""
    if request.method == 'POST':
        backup_type = request.POST.get('backup_type')
        notes = request.POST.get('notes', '')
        
        # 백업 생성 (실제 백업 로직은 별도 구현 필요)
        backup = DataBackup.objects.create(
            backup_type=backup_type,
            file_path=f'/backups/{backup_type.lower()}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.sql',
            status='PENDING',
            created_by=request.user,
            notes=notes,
        )
        
        # 관리자 액션 로그 기록
        AdminAction.objects.create(
            admin_user=request.user,
            action_type='BACKUP',
            target_model='DataBackup',
            target_id=backup.id,
            description=f'데이터 백업 요청: {backup.get_backup_type_display()}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        messages.success(request, '백업이 요청되었습니다.')
        return redirect('admin_panel:data_backup')
    
    backups = DataBackup.objects.all()
    context = {
        'backups': backups,
        'backup_types': DataBackup.BACKUP_TYPES,
    }
    
    return render(request, 'OilNote_AdminApp/data_backup.html', context)

@login_required
@user_passes_test(is_admin)
def maintenance_schedule(request):
    """유지보수 일정 관리"""
    if request.method == 'POST':
        title = request.POST.get('title')
        maintenance_type = request.POST.get('maintenance_type')
        description = request.POST.get('description')
        scheduled_start = request.POST.get('scheduled_start')
        scheduled_end = request.POST.get('scheduled_end')
        
        maintenance = MaintenanceSchedule.objects.create(
            title=title,
            maintenance_type=maintenance_type,
            description=description,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            created_by=request.user,
        )
        
        # 관리자 액션 로그 기록
        AdminAction.objects.create(
            admin_user=request.user,
            action_type='SYSTEM_CONFIG',
            target_model='MaintenanceSchedule',
            target_id=maintenance.id,
            description=f'유지보수 일정 생성: {title}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        messages.success(request, '유지보수 일정이 생성되었습니다.')
        return redirect('admin_panel:maintenance_schedule')
    
    schedules = MaintenanceSchedule.objects.all()
    context = {
        'schedules': schedules,
        'maintenance_types': MaintenanceSchedule.MAINTENANCE_TYPES,
    }
    
    return render(request, 'OilNote_AdminApp/maintenance_schedule.html', context)

@login_required
@user_passes_test(is_admin)
def user_management(request):
    """사용자 관리"""
    users = CustomUser.objects.all()
    
    # 필터링
    user_type = request.GET.get('user_type')
    if user_type:
        users = users.filter(user_type=user_type)
    
    # 검색
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # 페이지네이션
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_types': CustomUser.USER_TYPE_CHOICES,
        'current_filters': {
            'user_type': user_type,
            'search': search,
        }
    }
    
    return render(request, 'OilNote_AdminApp/user_management.html', context)

@login_required
@user_passes_test(is_admin)
def system_statistics(request):
    """시스템 통계"""
    # 사용자 통계
    user_stats = {
        'total': CustomUser.objects.count(),
        'customers': CustomUser.objects.filter(user_type='CUSTOMER').count(),
        'stations': CustomUser.objects.filter(user_type='STATION').count(),
        'active_today': CustomUser.objects.filter(last_login__date=timezone.now().date()).count(),
    }
    
    # 매출 통계
    sales_stats = {
        'total_sales': ExcelSalesData.objects.count(),
        'today_sales': ExcelSalesData.objects.filter(sale_date=timezone.now().date()).count(),
        'total_amount': ExcelSalesData.objects.aggregate(total=Sum('total_amount'))['total'] or 0,
    }
    
    # 카드 통계
    card_stats = {
        'total_cards': PointCard.objects.count(),
        'used_cards': PointCard.objects.filter(is_used=True).count(),
        'unused_cards': PointCard.objects.filter(is_used=False).count(),
    }
    
    # 최근 활동
    recent_activities = AdminAction.objects.all()[:20]
    
    context = {
        'user_stats': user_stats,
        'sales_stats': sales_stats,
        'card_stats': card_stats,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'OilNote_AdminApp/system_statistics.html', context)
