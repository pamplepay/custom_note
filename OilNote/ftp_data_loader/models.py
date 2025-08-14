from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class FTPServerConfig(models.Model):
    """FTP 서버 설정 모델"""
    name = models.CharField(max_length=100, verbose_name="설정명")
    host = models.CharField(max_length=255, verbose_name="FTP 호스트")
    port = models.IntegerField(default=21, verbose_name="포트")
    username = models.CharField(max_length=100, verbose_name="사용자명")
    password = models.CharField(max_length=255, verbose_name="비밀번호")
    remote_path = models.CharField(max_length=500, verbose_name="원격 경로", default="/")
    local_path = models.CharField(max_length=500, verbose_name="로컬 저장 경로")
    file_pattern = models.CharField(max_length=200, verbose_name="파일 패턴", default="*.xlsx")
    is_active = models.BooleanField(default=True, verbose_name="활성화")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    class Meta:
        verbose_name = "FTP 서버 설정"
        verbose_name_plural = "FTP 서버 설정"
    
    def __str__(self):
        return f"{self.name} ({self.host})"


class FTPDataLog(models.Model):
    """FTP 데이터 로그 모델"""
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('downloading', '다운로드 중'),
        ('completed', '완료'),
        ('failed', '실패'),
        ('processing', '처리 중'),
    ]
    
    server_config = models.ForeignKey(FTPServerConfig, on_delete=models.CASCADE, verbose_name="FTP 설정")
    filename = models.CharField(max_length=255, verbose_name="파일명")
    remote_path = models.CharField(max_length=500, verbose_name="원격 경로")
    local_path = models.CharField(max_length=500, verbose_name="로컬 경로")
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name="파일 크기")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="상태")
    error_message = models.TextField(blank=True, null=True, verbose_name="오류 메시지")
    downloaded_at = models.DateTimeField(null=True, blank=True, verbose_name="다운로드 완료일")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="처리 완료일")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    class Meta:
        verbose_name = "FTP 데이터 로그"
        verbose_name_plural = "FTP 데이터 로그"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.filename} - {self.get_status_display()}"


class FTPDataSchedule(models.Model):
    """FTP 데이터 스케줄 모델"""
    SCHEDULE_CHOICES = [
        ('hourly', '매시간'),
        ('daily', '매일'),
        ('weekly', '매주'),
        ('monthly', '매월'),
        ('custom', '사용자 정의'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="스케줄명")
    server_config = models.ForeignKey(FTPServerConfig, on_delete=models.CASCADE, verbose_name="FTP 설정")
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, verbose_name="스케줄 타입")
    cron_expression = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cron 표현식")
    is_active = models.BooleanField(default=True, verbose_name="활성화")
    last_run = models.DateTimeField(null=True, blank=True, verbose_name="마지막 실행")
    next_run = models.DateTimeField(null=True, blank=True, verbose_name="다음 실행")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    class Meta:
        verbose_name = "FTP 데이터 스케줄"
        verbose_name_plural = "FTP 데이터 스케줄"
    
    def __str__(self):
        return f"{self.name} - {self.get_schedule_type_display()}"
