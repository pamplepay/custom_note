from django.contrib import admin
from .models import SystemLog, AdminAction, SystemConfig, DataBackup, MaintenanceSchedule

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ['log_type', 'message', 'user', 'ip_address', 'created_at']
    list_filter = ['log_type', 'created_at']
    search_fields = ['message', 'user__username', 'ip_address']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        return False  # 시스템에서만 생성되도록 제한

@admin.register(AdminAction)
class AdminActionAdmin(admin.ModelAdmin):
    list_display = ['admin_user', 'action_type', 'target_model', 'target_id', 'ip_address', 'created_at']
    list_filter = ['action_type', 'created_at', 'admin_user']
    search_fields = ['admin_user__username', 'description', 'target_model']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['config_key', 'config_value', 'config_type', 'is_active', 'updated_at']
    list_filter = ['config_type', 'is_active', 'updated_at']
    search_fields = ['config_key', 'config_value', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['config_type', 'config_key']

@admin.register(DataBackup)
class DataBackupAdmin(admin.ModelAdmin):
    list_display = ['backup_type', 'file_path', 'file_size', 'status', 'created_by', 'created_at']
    list_filter = ['backup_type', 'status', 'created_at']
    search_fields = ['file_path', 'created_by__username', 'notes']
    readonly_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']

@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ['title', 'maintenance_type', 'scheduled_start', 'scheduled_end', 'status', 'created_by']
    list_filter = ['maintenance_type', 'status', 'scheduled_start']
    search_fields = ['title', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-scheduled_start']
