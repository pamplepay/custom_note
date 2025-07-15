import os
import logging
from ftplib import FTP
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import FTPServerConfig, FTPDataLog

logger = logging.getLogger(__name__)


class FTPDataService:
    """FTP 데이터 서비스 클래스"""
    
    def __init__(self, server_config: FTPServerConfig):
        self.server_config = server_config
        self.ftp = None
    
    def connect(self):
        """FTP 서버에 연결"""
        try:
            self.ftp = FTP()
            self.ftp.connect(self.server_config.host, self.server_config.port)
            self.ftp.login(self.server_config.username, self.server_config.password)
            logger.info(f"FTP 연결 성공: {self.server_config.host}")
            return True
        except Exception as e:
            logger.error(f"FTP 연결 실패: {self.server_config.host} - {str(e)}")
            return False
    
    def disconnect(self):
        """FTP 연결 해제"""
        if self.ftp:
            try:
                self.ftp.quit()
                logger.info("FTP 연결 해제")
            except Exception as e:
                logger.error(f"FTP 연결 해제 실패: {str(e)}")
    
    def list_files(self, remote_path=None):
        """원격 디렉토리의 파일 목록 조회"""
        if not self.ftp:
            if not self.connect():
                return []
        
        try:
            path = remote_path or self.server_config.remote_path
            files = []
            self.ftp.cwd(path)
            file_list = self.ftp.nlst()
            
            for filename in file_list:
                if self._matches_pattern(filename):
                    try:
                        size = self.ftp.size(filename)
                        files.append({
                            'name': filename,
                            'size': size,
                            'path': path
                        })
                    except Exception as e:
                        logger.warning(f"파일 정보 조회 실패: {filename} - {str(e)}")
                        continue
            
            return files
        except Exception as e:
            logger.error(f"파일 목록 조회 실패: {str(e)}")
            return []
    
    def _matches_pattern(self, filename):
        """파일명이 패턴과 일치하는지 확인"""
        import fnmatch
        return fnmatch.fnmatch(filename, self.server_config.file_pattern)
    
    def download_file(self, remote_filename, local_filename=None):
        """파일 다운로드"""
        if not self.ftp:
            if not self.connect():
                return False
        
        try:
            # 로컬 파일명 설정
            if not local_filename:
                local_filename = os.path.join(
                    self.server_config.local_path,
                    remote_filename
                )
            
            # 로컬 디렉토리 생성
            os.makedirs(os.path.dirname(local_filename), exist_ok=True)
            
            # 파일 다운로드
            with open(local_filename, 'wb') as local_file:
                self.ftp.retrbinary(f'RETR {remote_filename}', local_file.write)
            
            logger.info(f"파일 다운로드 완료: {remote_filename} -> {local_filename}")
            return True
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {remote_filename} - {str(e)}")
            return False
    
    def download_all_files(self):
        """모든 파일 다운로드"""
        files = self.list_files()
        downloaded_files = []
        
        for file_info in files:
            try:
                # 로그 생성
                log_entry = FTPDataLog.objects.create(
                    server_config=self.server_config,
                    filename=file_info['name'],
                    remote_path=file_info['path'],
                    local_path=os.path.join(self.server_config.local_path, file_info['name']),
                    file_size=file_info['size'],
                    status='downloading'
                )
                
                # 파일 다운로드
                if self.download_file(file_info['name']):
                    log_entry.status = 'completed'
                    log_entry.downloaded_at = timezone.now()
                    log_entry.save()
                    downloaded_files.append(file_info['name'])
                    logger.info(f"파일 다운로드 완료: {file_info['name']}")
                else:
                    log_entry.status = 'failed'
                    log_entry.error_message = f"다운로드 실패: {file_info['name']}"
                    log_entry.save()
                    logger.error(f"파일 다운로드 실패: {file_info['name']}")
                
            except Exception as e:
                logger.error(f"파일 처리 중 오류: {file_info['name']} - {str(e)}")
                continue
        
        return downloaded_files
    
    def process_downloaded_files(self):
        """다운로드된 파일 처리"""
        # 여기에 파일 처리 로직을 추가할 수 있습니다
        # 예: 엑셀 파일 분석, 데이터베이스 저장 등
        pass


class FTPDataManager:
    """FTP 데이터 관리자 클래스"""
    
    @staticmethod
    def download_from_all_servers():
        """모든 활성화된 FTP 서버에서 파일 다운로드"""
        active_configs = FTPServerConfig.objects.filter(is_active=True)
        
        for config in active_configs:
            try:
                service = FTPDataService(config)
                downloaded_files = service.download_all_files()
                service.disconnect()
                
                logger.info(f"서버 {config.name}에서 {len(downloaded_files)}개 파일 다운로드 완료")
                
            except Exception as e:
                logger.error(f"서버 {config.name} 처리 중 오류: {str(e)}")
                continue
    
    @staticmethod
    def get_download_logs(server_config=None, status=None, limit=50):
        """다운로드 로그 조회"""
        queryset = FTPDataLog.objects.all()
        
        if server_config:
            queryset = queryset.filter(server_config=server_config)
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset[:limit]
    
    @staticmethod
    def cleanup_old_logs(days=30):
        """오래된 로그 정리"""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count = FTPDataLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"{deleted_count}개의 오래된 로그 삭제 완료")
        return deleted_count 