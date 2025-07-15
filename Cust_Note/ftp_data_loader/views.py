from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import FTPServerConfig, FTPDataLog, FTPDataSchedule
from .services import FTPDataService, FTPDataManager
import json
import logging

logger = logging.getLogger(__name__)


@login_required
def ftp_dashboard(request):
    """FTP 데이터 대시보드"""
    # FTP 서버 설정 통계
    total_configs = FTPServerConfig.objects.count()
    active_configs = FTPServerConfig.objects.filter(is_active=True).count()
    
    # 최근 다운로드 로그
    recent_logs = FTPDataLog.objects.select_related('server_config').order_by('-created_at')[:10]
    
    # 상태별 통계
    status_stats = {
        'completed': FTPDataLog.objects.filter(status='completed').count(),
        'failed': FTPDataLog.objects.filter(status='failed').count(),
        'pending': FTPDataLog.objects.filter(status='pending').count(),
        'downloading': FTPDataLog.objects.filter(status='downloading').count(),
    }
    
    context = {
        'total_configs': total_configs,
        'active_configs': active_configs,
        'recent_logs': recent_logs,
        'status_stats': status_stats,
    }
    
    return render(request, 'ftp_data_loader/dashboard.html', context)


@login_required
def ftp_server_list(request):
    """FTP 서버 설정 목록"""
    servers = FTPServerConfig.objects.all().order_by('-created_at')
    
    # 검색 기능
    search_query = request.GET.get('search', '')
    if search_query:
        servers = servers.filter(
            Q(name__icontains=search_query) |
            Q(host__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    # 페이지네이션
    paginator = Paginator(servers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'ftp_data_loader/server_list.html', context)


@login_required
def ftp_server_detail(request, server_id):
    """FTP 서버 설정 상세"""
    server = get_object_or_404(FTPServerConfig, id=server_id)
    
    # 해당 서버의 다운로드 로그
    logs = FTPDataLog.objects.filter(server_config=server).order_by('-created_at')[:20]
    
    context = {
        'server': server,
        'logs': logs,
    }
    
    return render(request, 'ftp_data_loader/server_detail.html', context)


@login_required
def ftp_server_create(request):
    """FTP 서버 설정 생성"""
    if request.method == 'POST':
        try:
            server = FTPServerConfig.objects.create(
                name=request.POST.get('name'),
                host=request.POST.get('host'),
                port=int(request.POST.get('port', 21)),
                username=request.POST.get('username'),
                password=request.POST.get('password'),
                remote_path=request.POST.get('remote_path', '/'),
                local_path=request.POST.get('local_path'),
                file_pattern=request.POST.get('file_pattern', '*.xlsx'),
                is_active=request.POST.get('is_active') == 'on'
            )
            messages.success(request, 'FTP 서버 설정이 생성되었습니다.')
            return redirect('ftp_data_loader:server_detail', server_id=server.id)
        except Exception as e:
            messages.error(request, f'FTP 서버 설정 생성 중 오류가 발생했습니다: {str(e)}')
    
    return render(request, 'ftp_data_loader/server_form.html')


@login_required
def ftp_server_edit(request, server_id):
    """FTP 서버 설정 수정"""
    server = get_object_or_404(FTPServerConfig, id=server_id)
    
    if request.method == 'POST':
        try:
            server.name = request.POST.get('name')
            server.host = request.POST.get('host')
            server.port = int(request.POST.get('port', 21))
            server.username = request.POST.get('username')
            server.password = request.POST.get('password')
            server.remote_path = request.POST.get('remote_path', '/')
            server.local_path = request.POST.get('local_path')
            server.file_pattern = request.POST.get('file_pattern', '*.xlsx')
            server.is_active = request.POST.get('is_active') == 'on'
            server.save()
            
            messages.success(request, 'FTP 서버 설정이 수정되었습니다.')
            return redirect('ftp_data_loader:server_detail', server_id=server.id)
        except Exception as e:
            messages.error(request, f'FTP 서버 설정 수정 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'server': server,
    }
    
    return render(request, 'ftp_data_loader/server_form.html', context)


@login_required
def ftp_server_delete(request, server_id):
    """FTP 서버 설정 삭제"""
    server = get_object_or_404(FTPServerConfig, id=server_id)
    
    if request.method == 'POST':
        try:
            server.delete()
            messages.success(request, 'FTP 서버 설정이 삭제되었습니다.')
            return redirect('ftp_data_loader:server_list')
        except Exception as e:
            messages.error(request, f'FTP 서버 설정 삭제 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'server': server,
    }
    
    return render(request, 'ftp_data_loader/server_confirm_delete.html', context)


@login_required
def ftp_download_files(request, server_id):
    """FTP에서 파일 다운로드"""
    server = get_object_or_404(FTPServerConfig, id=server_id)
    
    if request.method == 'POST':
        try:
            service = FTPDataService(server)
            downloaded_files = service.download_all_files()
            service.disconnect()
            
            if downloaded_files:
                messages.success(request, f'{len(downloaded_files)}개 파일이 다운로드되었습니다.')
            else:
                messages.warning(request, '다운로드할 파일이 없습니다.')
                
        except Exception as e:
            messages.error(request, f'파일 다운로드 중 오류가 발생했습니다: {str(e)}')
    
    return redirect('ftp_data_loader:server_detail', server_id=server.id)


@login_required
def ftp_test_connection(request, server_id):
    """FTP 연결 테스트"""
    server = get_object_or_404(FTPServerConfig, id=server_id)
    
    try:
        service = FTPDataService(server)
        if service.connect():
            files = service.list_files()
            service.disconnect()
            
            return JsonResponse({
                'success': True,
                'message': f'연결 성공! {len(files)}개 파일 발견',
                'files': files
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'FTP 서버에 연결할 수 없습니다.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'연결 테스트 중 오류 발생: {str(e)}'
        })


@login_required
def ftp_log_list(request):
    """FTP 다운로드 로그 목록"""
    logs = FTPDataLog.objects.select_related('server_config').order_by('-created_at')
    
    # 필터링
    status_filter = request.GET.get('status', '')
    server_filter = request.GET.get('server', '')
    
    if status_filter:
        logs = logs.filter(status=status_filter)
    
    if server_filter:
        logs = logs.filter(server_config_id=server_filter)
    
    # 페이지네이션
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 필터 옵션
    servers = FTPServerConfig.objects.all()
    status_choices = FTPDataLog.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'servers': servers,
        'status_choices': status_choices,
        'status_filter': status_filter,
        'server_filter': server_filter,
    }
    
    return render(request, 'ftp_data_loader/log_list.html', context)


@login_required
def ftp_bulk_download(request):
    """모든 활성화된 FTP 서버에서 파일 다운로드"""
    if request.method == 'POST':
        try:
            FTPDataManager.download_from_all_servers()
            messages.success(request, '모든 FTP 서버에서 파일 다운로드가 완료되었습니다.')
        except Exception as e:
            messages.error(request, f'일괄 다운로드 중 오류가 발생했습니다: {str(e)}')
    
    return redirect('ftp_data_loader:dashboard')
