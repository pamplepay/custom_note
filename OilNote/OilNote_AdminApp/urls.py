from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # 대시보드
    path('', views.admin_dashboard, name='admin_dashboard'),
    
    # 시스템 관리
    path('logs/', views.system_logs, name='system_logs'),
    path('actions/', views.admin_actions, name='admin_actions'),
    path('config/', views.system_config, name='system_config'),
    
    # 데이터 관리
    path('backup/', views.data_backup, name='data_backup'),
    path('maintenance/', views.maintenance_schedule, name='maintenance_schedule'),
    
    # 사용자 관리
    path('users/', views.user_management, name='user_management'),
    
    # 통계
    path('statistics/', views.system_statistics, name='system_statistics'),
]
