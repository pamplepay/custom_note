from django.urls import path
from . import views

app_name = 'ftp_data_loader'

urlpatterns = [
    # 대시보드
    path('', views.ftp_dashboard, name='dashboard'),
    
    # FTP 서버 관리
    path('servers/', views.ftp_server_list, name='server_list'),
    path('servers/create/', views.ftp_server_create, name='server_create'),
    path('servers/<int:server_id>/', views.ftp_server_detail, name='server_detail'),
    path('servers/<int:server_id>/edit/', views.ftp_server_edit, name='server_edit'),
    path('servers/<int:server_id>/delete/', views.ftp_server_delete, name='server_delete'),
    
    # FTP 작업
    path('servers/<int:server_id>/download/', views.ftp_download_files, name='download_files'),
    path('servers/<int:server_id>/test/', views.ftp_test_connection, name='test_connection'),
    path('bulk-download/', views.ftp_bulk_download, name='bulk_download'),
    
    # 로그 관리
    path('logs/', views.ftp_log_list, name='log_list'),
] 