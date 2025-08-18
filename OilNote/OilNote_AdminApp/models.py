from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class SystemLog(models.Model):
    """시스템 로그 모델"""
    LOG_TYPES = [
        ('INFO', '정보'),
        ('WARNING', '경고'),
        ('ERROR', '오류'),
        ('DEBUG', '디버그'),
    ]
    
    log_type = models.CharField(max_length=10, choices=LOG_TYPES, verbose_name='로그 유형')
    message = models.TextField(verbose_name='로그 메시지')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='관련 사용자')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP 주소')
    user_agent = models.TextField(blank=True, null=True, verbose_name='사용자 에이전트')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    
    class Meta:
        verbose_name = '시스템 로그'
        verbose_name_plural = '시스템 로그 목록'
        ordering = ['-created_at']
        db_table = 'OilNote_AdminApp_systemlog'
    
    def __str__(self):
        return f"[{self.log_type}] {self.message[:50]}... ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class AdminAction(models.Model):
    """관리자 액션 로그 모델"""
    ACTION_TYPES = [
        ('USER_CREATE', '사용자 생성'),
        ('USER_UPDATE', '사용자 수정'),
        ('USER_DELETE', '사용자 삭제'),
        ('STATION_CREATE', '주유소 생성'),
        ('STATION_UPDATE', '주유소 수정'),
        ('STATION_DELETE', '주유소 삭제'),
        ('COUPON_ISSUE', '쿠폰 발행'),
        ('COUPON_REVOKE', '쿠폰 취소'),
        ('DATA_EXPORT', '데이터 내보내기'),
        ('DATA_IMPORT', '데이터 가져오기'),
        ('SYSTEM_CONFIG', '시스템 설정 변경'),
        ('BACKUP', '백업'),
        ('RESTORE', '복원'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='관리자')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name='액션 유형')
    target_model = models.CharField(max_length=50, blank=True, null=True, verbose_name='대상 모델')
    target_id = models.IntegerField(blank=True, null=True, verbose_name='대상 ID')
    description = models.TextField(verbose_name='설명')
    details = models.JSONField(default=dict, blank=True, verbose_name='상세 정보')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP 주소')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    
    class Meta:
        verbose_name = '관리자 액션'
        verbose_name_plural = '관리자 액션 목록'
        ordering = ['-created_at']
        db_table = 'OilNote_AdminApp_adminaction'
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.get_action_type_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class SystemConfig(models.Model):
    """시스템 설정 모델"""
    CONFIG_TYPES = [
        ('GENERAL', '일반 설정'),
        ('SECURITY', '보안 설정'),
        ('EMAIL', '이메일 설정'),
        ('NOTIFICATION', '알림 설정'),
        ('BACKUP', '백업 설정'),
        ('MAINTENANCE', '유지보수 설정'),
    ]
    
    config_key = models.CharField(max_length=100, unique=True, verbose_name='설정 키')
    config_value = models.TextField(verbose_name='설정 값')
    config_type = models.CharField(max_length=20, choices=CONFIG_TYPES, verbose_name='설정 유형')
    description = models.TextField(blank=True, null=True, verbose_name='설명')
    is_active = models.BooleanField(default=True, verbose_name='활성화 여부')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        verbose_name = '시스템 설정'
        verbose_name_plural = '시스템 설정 목록'
        ordering = ['config_type', 'config_key']
        db_table = 'OilNote_AdminApp_systemconfig'
    
    def __str__(self):
        return f"{self.config_key} ({self.get_config_type_display()})"


class DataBackup(models.Model):
    """데이터 백업 모델"""
    BACKUP_TYPES = [
        ('FULL', '전체 백업'),
        ('INCREMENTAL', '증분 백업'),
        ('USER_DATA', '사용자 데이터'),
        ('SALES_DATA', '매출 데이터'),
        ('SYSTEM_DATA', '시스템 데이터'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('IN_PROGRESS', '진행 중'),
        ('COMPLETED', '완료'),
        ('FAILED', '실패'),
    ]
    
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, verbose_name='백업 유형')
    file_path = models.CharField(max_length=500, verbose_name='파일 경로')
    file_size = models.BigIntegerField(default=0, verbose_name='파일 크기 (bytes)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='상태')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='생성자')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='완료일시')
    notes = models.TextField(blank=True, null=True, verbose_name='비고')
    
    class Meta:
        verbose_name = '데이터 백업'
        verbose_name_plural = '데이터 백업 목록'
        ordering = ['-created_at']
        db_table = 'OilNote_AdminApp_databackup'
    
    def __str__(self):
        return f"{self.get_backup_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')} ({self.get_status_display()})"


class MaintenanceSchedule(models.Model):
    """유지보수 일정 모델"""
    MAINTENANCE_TYPES = [
        ('SYSTEM', '시스템 유지보수'),
        ('DATABASE', '데이터베이스 유지보수'),
        ('BACKUP', '백업 유지보수'),
        ('SECURITY', '보안 업데이트'),
        ('PERFORMANCE', '성능 최적화'),
    ]
    
    STATUS_CHOICES = [
        ('SCHEDULED', '예정됨'),
        ('IN_PROGRESS', '진행 중'),
        ('COMPLETED', '완료'),
        ('CANCELLED', '취소됨'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='제목')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES, verbose_name='유지보수 유형')
    description = models.TextField(verbose_name='설명')
    scheduled_start = models.DateTimeField(verbose_name='예정 시작 시간')
    scheduled_end = models.DateTimeField(verbose_name='예정 종료 시간')
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='실제 시작 시간')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='실제 종료 시간')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED', verbose_name='상태')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='생성자')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        verbose_name = '유지보수 일정'
        verbose_name_plural = '유지보수 일정 목록'
        ordering = ['-scheduled_start']
        db_table = 'OilNote_AdminApp_maintenanceschedule'
    
    def __str__(self):
        return f"{self.title} ({self.scheduled_start.strftime('%Y-%m-%d %H:%M')})"
