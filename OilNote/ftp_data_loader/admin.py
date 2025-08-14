from django.contrib import admin
from .models import FTPServerConfig, FTPDataLog, FTPDataSchedule


@admin.register(FTPServerConfig)
class FTPServerConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'port', 'username', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'host', 'username']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'host', 'port', 'username', 'password')
        }),
        ('경로 설정', {
            'fields': ('remote_path', 'local_path', 'file_pattern')
        }),
        ('상태', {
            'fields': ('is_active',)
        }),
        ('시간 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FTPDataLog)
class FTPDataLogAdmin(admin.ModelAdmin):
    list_display = ['filename', 'server_config', 'status', 'file_size', 'downloaded_at', 'created_at']
    list_filter = ['status', 'server_config', 'downloaded_at', 'created_at']
    search_fields = ['filename', 'server_config__name']
    readonly_fields = ['created_at', 'updated_at', 'downloaded_at', 'processed_at']
    fieldsets = (
        ('파일 정보', {
            'fields': ('server_config', 'filename', 'remote_path', 'local_path', 'file_size')
        }),
        ('상태 정보', {
            'fields': ('status', 'error_message')
        }),
        ('시간 정보', {
            'fields': ('downloaded_at', 'processed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FTPDataSchedule)
class FTPDataScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'server_config', 'schedule_type', 'is_active', 'last_run', 'next_run']
    list_filter = ['schedule_type', 'is_active', 'last_run', 'created_at']
    search_fields = ['name', 'server_config__name']
    readonly_fields = ['last_run', 'next_run', 'created_at', 'updated_at']
    fieldsets = (
        ('기본 정보', {
            'fields': ('name', 'server_config')
        }),
        ('스케줄 설정', {
            'fields': ('schedule_type', 'cron_expression')
        }),
        ('상태', {
            'fields': ('is_active',)
        }),
        ('실행 정보', {
            'fields': ('last_run', 'next_run'),
            'classes': ('collapse',)
        }),
        ('시간 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
