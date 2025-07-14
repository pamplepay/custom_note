from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from Cust_User.models import CustomUser, CustomerStationRelation
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Create your models here.

class PointCard(models.Model):
    """멤버십 카드 모델"""
    number = models.CharField(max_length=16, unique=True, help_text="16자리 카드번호")
    oil_company_code = models.CharField(max_length=1, verbose_name='정유사코드', help_text="정유사 코드 (1자리)", default='0')
    agency_code = models.CharField(max_length=3, verbose_name='대리점코드', help_text="대리점 코드 (3자리)", default='000')
    tids = models.JSONField(default=list, help_text="카드가 등록된 TID 목록")
    is_used = models.BooleanField(default=False, help_text="카드 사용 여부")
    created_at = models.DateTimeField(auto_now_add=True, help_text="카드 생성일시")
    updated_at = models.DateTimeField(auto_now=True, help_text="카드 수정일시")

    class Meta:
        verbose_name = "멤버십 카드"
        verbose_name_plural = "1. 멤버십 카드 목록"
        ordering = ['-created_at']

    def __str__(self):
        return f"카드번호: {self.full_number} (사용{'중' if self.is_used else '가능'})"

    @property
    def full_number(self):
        """20자리 전체 카드번호 반환"""
        return f"{self.oil_company_code}{self.agency_code}{self.number}"

    def add_tid(self, tid):
        """TID를 카드에 추가"""
        logger.info(f"카드 {self.number}에 TID {tid} 추가 시도")
        logger.debug(f"현재 TID 목록: {self.tids}")
        
        if not isinstance(self.tids, list):
            logger.warning(f"카드 {self.number}의 tids가 리스트가 아님: {type(self.tids)}")
            self.tids = []
        
        if tid not in self.tids:
            logger.info(f"새로운 TID {tid} 추가")
            self.tids.append(tid)
            try:
                self.save()
                logger.info(f"카드 {self.number}에 TID {tid} 추가 성공")
                logger.debug(f"업데이트된 TID 목록: {self.tids}")
                return True
            except Exception as e:
                logger.error(f"카드 {self.number}에 TID {tid} 추가 중 오류 발생: {str(e)}")
                return False
        else:
            logger.info(f"TID {tid}가 이미 카드 {self.number}에 존재함")
            return False

    def remove_tid(self, tid):
        """TID를 카드에서 제거"""
        logger.info(f"카드 {self.number}에서 TID {tid} 제거 시도")
        logger.debug(f"현재 TID 목록: {self.tids}")
        
        if not isinstance(self.tids, list):
            logger.warning(f"카드 {self.number}의 tids가 리스트가 아님: {type(self.tids)}")
            return False
        
        if tid in self.tids:
            logger.info(f"TID {tid} 제거")
            self.tids.remove(tid)
            try:
                self.save()
                logger.info(f"카드 {self.number}에서 TID {tid} 제거 성공")
                logger.debug(f"업데이트된 TID 목록: {self.tids}")
                return True
            except Exception as e:
                logger.error(f"카드 {self.number}에서 TID {tid} 제거 중 오류 발생: {str(e)}")
                return False
        else:
            logger.info(f"TID {tid}가 카드 {self.number}에 존재하지 않음")
            return False

class StationCardMapping(models.Model):
    card = models.ForeignKey(
        PointCard, 
        on_delete=models.CASCADE,
        verbose_name='포인트카드',
        related_name='mappings'
    )
    registered_at = models.DateTimeField(default=timezone.now, verbose_name='등록일')
    is_active = models.BooleanField(default=True, verbose_name='활성화 여부')
    tid = models.CharField(max_length=50, blank=True, null=True, verbose_name='주유소 TID')

    class Meta:
        verbose_name = '주유소-카드 매핑'
        verbose_name_plural = '주유소-카드 매핑'
        ordering = ['-registered_at']

    def __str__(self):
        return f"카드 {self.card.number} (TID: {self.tid or '미설정'})"

    def save(self, *args, **kwargs):
        logger.info(f"StationCardMapping 저장 시도: 카드={self.card.number}, TID={self.tid}")
        
        if self.tid:
            logger.debug(f"카드 {self.card.number}의 현재 TID 목록: {self.card.tids}")
            try:
                # TID를 카드의 tids 리스트에 추가
                if not isinstance(self.card.tids, list):
                    logger.warning(f"카드 {self.card.number}의 tids가 리스트가 아님: {type(self.card.tids)}")
                    self.card.tids = []
                
                if self.tid not in self.card.tids:
                    logger.info(f"카드 {self.card.number}에 새로운 TID {self.tid} 추가")
                    self.card.tids.append(self.tid)
                    self.card.save()
                    logger.debug(f"카드 {self.card.number}의 업데이트된 TID 목록: {self.card.tids}")
            except Exception as e:
                logger.error(f"카드 {self.card.number}에 TID {self.tid} 추가 중 오류 발생: {str(e)}")
        
        try:
            super().save(*args, **kwargs)
            logger.info(f"StationCardMapping 저장 성공: 카드={self.card.number}, TID={self.tid}")
        except Exception as e:
            logger.error(f"StationCardMapping 저장 중 오류 발생: {str(e)}")
            raise
    
    def delete(self, *args, **kwargs):
        logger.info(f"StationCardMapping 삭제 시도: 카드={self.card.number}, TID={self.tid}")
        
        if self.tid:
            logger.debug(f"카드 {self.card.number}의 현재 TID 목록: {self.card.tids}")
            try:
                # TID를 카드의 tids 리스트에서 제거
                if self.tid in self.card.tids:
                    logger.info(f"카드 {self.card.number}에서 TID {self.tid} 제거")
                    self.card.tids.remove(self.tid)
                    self.card.save()
                    logger.debug(f"카드 {self.card.number}의 업데이트된 TID 목록: {self.card.tids}")
            except Exception as e:
                logger.error(f"카드 {self.card.number}에서 TID {self.tid} 제거 중 오류 발생: {str(e)}")
        
        try:
            super().delete(*args, **kwargs)
            logger.info(f"StationCardMapping 삭제 성공: 카드={self.card.number}, TID={self.tid}")
        except Exception as e:
            logger.error(f"StationCardMapping 삭제 중 오류 발생: {str(e)}")
            raise

class StationList(get_user_model()):
    class Meta:
        proxy = True
        verbose_name = '주유소'
        verbose_name_plural = '2. 주유소 목록'

    def __str__(self):
        return self.username if hasattr(self, 'username') else str(self.id)

class SalesData(models.Model):
    """매출 데이터 모델"""
    station = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    upload_date = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)  # 저장된 파일 경로
    original_file_name = models.CharField(max_length=255)  # 원본 파일명
    sales_date = models.DateField()  # 매출 날짜
    total_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # 총 매출액

    class Meta:
        ordering = ['-sales_date']
        unique_together = ['station', 'sales_date']  # 같은 날짜에 대한 중복 데이터 방지

    def __str__(self):
        return f"{self.station.username} - {self.sales_date} ({self.total_sales}원)"

class ExcelSalesData(models.Model):
    """엑셀 파일에서 읽어온 상세 매출 데이터 모델"""
    tid = models.CharField(max_length=50, blank=True, null=True, verbose_name='주유소 TID')
    blank_column = models.CharField(max_length=10, blank=True, null=True, verbose_name='공백')
    sale_date = models.DateField(verbose_name='판매일자')
    sale_time = models.TimeField(verbose_name='주유시간')
    customer_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='고객번호')
    customer_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='고객명')
    issue_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='발행번호')
    product_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='주류상품종류')
    sale_type = models.CharField(max_length=20, blank=True, null=True, verbose_name='판매구분')
    payment_type = models.CharField(max_length=20, blank=True, null=True, verbose_name='결제구분')
    sale_type2 = models.CharField(max_length=20, blank=True, null=True, verbose_name='판매구분2')
    nozzle = models.CharField(max_length=20, blank=True, null=True, verbose_name='노즐')
    product_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='제품코드')
    product_pack = models.CharField(max_length=50, blank=True, null=True, verbose_name='제품/PACK')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='판매수량')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='판매단가')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='판매금액')
    earned_points = models.IntegerField(default=0, verbose_name='적립포인트')
    points = models.IntegerField(default=0, verbose_name='포인트')
    bonus = models.IntegerField(default=0, verbose_name='보너스')
    pos_id = models.CharField(max_length=20, blank=True, null=True, verbose_name='POS_ID')
    pos_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='POS코드')
    store = models.CharField(max_length=50, blank=True, null=True, verbose_name='판매점')
    receipt = models.CharField(max_length=50, blank=True, null=True, verbose_name='영수증')
    approval_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='승인번호')
    approval_datetime = models.DateTimeField(null=True, blank=True, verbose_name='승인일시')
    bonus_card = models.CharField(max_length=20, blank=True, null=True, verbose_name='보너스카드')
    customer_card_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='고객카드번호')
    data_created_at = models.DateTimeField(null=True, blank=True, verbose_name='데이터생성일시')
    source_file = models.CharField(max_length=255, blank=True, null=True, verbose_name='원본 파일명')

    class Meta:
        verbose_name = '엑셀 매출 데이터'
        verbose_name_plural = '5. 엑셀 매출 데이터 목록'
        ordering = ['-sale_date', '-sale_time']

    def __str__(self):
        return f"{self.sale_date} - {self.product_pack} - {self.total_amount}원"

class SalesStatistics(models.Model):
    """매출 통계 데이터 모델"""
    tid = models.CharField(max_length=50, blank=True, null=True, verbose_name='주유소 TID')
    sale_date = models.DateField(verbose_name='판매일자')
    total_transactions = models.IntegerField(default=0, verbose_name='총 거래건수')
    total_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='총 판매수량')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='총 판매금액')
    avg_unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='평균 단가')
    top_product = models.CharField(max_length=100, blank=True, null=True, verbose_name='최다 판매 제품')
    top_product_count = models.IntegerField(default=0, verbose_name='최다 판매 제품 수량')
    source_file = models.CharField(max_length=255, blank=True, null=True, verbose_name='원본파일명')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        verbose_name = '매출 통계'
        verbose_name_plural = '4. 매출 통계 목록'
        ordering = ['-sale_date', '-created_at']
        unique_together = ['tid', 'sale_date']

    def __str__(self):
        return f"{self.tid} - {self.sale_date} ({self.total_transactions}건, {self.total_amount:,.0f}원)"


class MonthlySalesStatistics(models.Model):
    """월별 누적 매출 통계 데이터 모델"""
    tid = models.CharField(max_length=50, blank=True, null=True, verbose_name='주유소 TID')
    year_month = models.CharField(max_length=7, verbose_name='년월 (YYYY-MM)')
    total_transactions = models.IntegerField(default=0, verbose_name='총 거래건수')
    total_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='총 판매수량')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='총 판매금액')
    avg_unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='평균 단가')
    top_product = models.CharField(max_length=100, blank=True, null=True, verbose_name='최다 판매 제품')
    top_product_count = models.IntegerField(default=0, verbose_name='최다 판매 제품 수량')
    product_breakdown = models.JSONField(default=dict, verbose_name='유종별 판매 현황')
    
    # 제품별 상세 누적 데이터
    product_sales_count = models.JSONField(default=dict, verbose_name='제품별 판매횟수')
    product_sales_quantity = models.JSONField(default=dict, verbose_name='제품별 판매수량')
    product_sales_amount = models.JSONField(default=dict, verbose_name='제품별 판매금액')
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name='업데이트일시')

    class Meta:
        verbose_name = '월별 매출 통계'
        verbose_name_plural = '6. 월별 매출 통계 목록'
        ordering = ['-year_month']
        unique_together = ['tid', 'year_month']

    def __str__(self):
        return f"{self.tid} - {self.year_month} ({self.total_transactions}건, {self.total_amount:,.0f}원)"
