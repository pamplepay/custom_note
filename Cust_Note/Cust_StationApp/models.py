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

class Group(models.Model):
    """고객 그룹 모델"""
    name = models.CharField(max_length=100, verbose_name='그룹명', help_text="고객 그룹 이름")
    station = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='주유소', help_text="그룹을 생성한 주유소")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        verbose_name = '고객 그룹'
        verbose_name_plural = '0. 고객 그룹 목록'
        ordering = ['-created_at']
        unique_together = ['name', 'station']  # 같은 주유소 내에서 그룹명 중복 방지

    def __str__(self):
        return f"{self.station.username} - {self.name}"

    def get_customer_count(self):
        """이 그룹에 속한 고객 수 반환"""
        from Cust_User.models import CustomerProfile
        return CustomerProfile.objects.filter(group=self.name).count()

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
        verbose_name_plural = '7. 주유소-카드 매핑'
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

class PhoneCardMapping(models.Model):
    """폰번호와 멤버십카드 연동 모델"""
    phone_number = models.CharField(
        max_length=15, 
        verbose_name='전화번호',
        help_text='하이픈(-) 없이 숫자만 입력 (예: 01012345678)',
        validators=[
            RegexValidator(
                regex=r'^01[0-9]{8,9}$',
                message='올바른 휴대폰 번호를 입력해주세요. (예: 01012345678)'
            )
        ]
    )
    membership_card = models.ForeignKey(
        'PointCard',
        on_delete=models.CASCADE,
        verbose_name='멤버십 카드',
        related_name='phone_mappings'
    )
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='등록 주유소',
        limit_choices_to={'user_type': 'STATION'}
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name='사용 여부',
        help_text='고객이 회원가입하여 연동되었는지 여부'
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='연동된 사용자',
        related_name='phone_card_mappings',
        limit_choices_to={'user_type': 'CUSTOMER'}
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='등록일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')

    class Meta:
        verbose_name = '폰번호-카드 연동'
        verbose_name_plural = '6. 폰번호-카드 연동 목록'
        ordering = ['-created_at']
        # unique_together 제거 - 폰번호 하나에 여러 카드 등록 가능
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['membership_card']),
            models.Index(fields=['is_used']),
        ]

    def __str__(self):
        status = "연동됨" if self.is_used else "미연동"
        return f"{self.phone_number} - {self.membership_card.full_number} ({status})"

    def clean(self):
        """데이터 검증"""
        from django.core.exceptions import ValidationError
        
        # 폰번호 형식 정리 (하이픈 제거)
        if self.phone_number:
            self.phone_number = self.phone_number.replace('-', '').replace(' ', '')
        
        # 같은 폰번호와 카드 조합이 이미 존재하는지 확인 (중복 등록 방지)
        existing_mapping = PhoneCardMapping.objects.filter(
            phone_number=self.phone_number,
            membership_card=self.membership_card,
            station=self.station
        ).exclude(pk=self.pk)
        
        if existing_mapping.exists():
            raise ValidationError('이 폰번호와 카드 조합은 이미 등록되어 있습니다.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def find_by_phone(cls, phone_number, station=None):
        """폰번호로 연동 정보 찾기 (미사용 상태 우선)"""
        phone_number = phone_number.replace('-', '').replace(' ', '')
        queryset = cls.objects.filter(phone_number=phone_number)
        
        if station:
            queryset = queryset.filter(station=station)
        
        # 미사용 상태인 매핑을 우선적으로 반환
        unused_mapping = queryset.filter(is_used=False).first()
        if unused_mapping:
            return unused_mapping
        
        # 미사용 상태가 없으면 첫 번째 매핑 반환
        return queryset.first()

    @classmethod
    def find_all_by_phone(cls, phone_number, station=None):
        """폰번호로 모든 연동 정보 찾기"""
        phone_number = phone_number.replace('-', '').replace(' ', '')
        queryset = cls.objects.filter(phone_number=phone_number)
        
        if station:
            queryset = queryset.filter(station=station)
        
        return queryset.order_by('-is_used', '-created_at')  # 미사용 상태 우선, 최신 등록 우선

    def link_to_user(self, user):
        """사용자와 연동"""
        if user.user_type != 'CUSTOMER':
            raise ValueError('일반 고객만 연동할 수 있습니다.')
        
        # 이미 사용 중인 카드인지 확인 (다른 PhoneCardMapping에서 사용 중인지 확인)
        existing_used_mapping = PhoneCardMapping.objects.filter(
            membership_card=self.membership_card,
            is_used=True
        ).exclude(pk=self.pk)
        
        if existing_used_mapping.exists():
            # 이미 다른 매핑에서 사용 중인 카드라면 연동 불가
            raise ValueError('이미 다른 사용자와 연동된 멤버십 카드입니다.')
        
        self.linked_user = user
        self.is_used = True
        self.save()
        
        # 고객 프로필에 멤버십 카드 정보 업데이트
        if hasattr(user, 'customer_profile'):
            # 기존 멤버십카드가 있으면 추가, 없으면 새로 설정
            current_cards = user.customer_profile.membership_card or ''
            if current_cards:
                if self.membership_card.full_number not in current_cards:
                    user.customer_profile.membership_card = f"{current_cards},{self.membership_card.full_number}"
            else:
                user.customer_profile.membership_card = self.membership_card.full_number
            user.customer_profile.save()
        
        # 주유소와 고객 관계 생성
        from Cust_User.models import CustomerStationRelation
        CustomerStationRelation.objects.get_or_create(
            customer=user,
            station=self.station,
            defaults={'is_active': True}
        )
        
        logger.info(f"폰번호 {self.phone_number}과 사용자 {user.username} 연동 완료")

    def unlink_user(self):
        """사용자 연동 해제"""
        self.linked_user = None
        self.is_used = False
        self.save()
        
        logger.info(f"폰번호 {self.phone_number} 사용자 연동 해제")

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
        verbose_name_plural = '4. 엑셀 매출 데이터 목록'
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
        verbose_name_plural = '3. 매출 통계 목록'
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
        verbose_name_plural = '5. 월별 매출 통계 목록'
        ordering = ['-year_month']
        unique_together = ['tid', 'year_month']

    def __str__(self):
        return f"{self.tid} - {self.year_month} ({self.total_transactions}건, {self.total_amount:,.0f}원)"

class Coupon(models.Model):
    """쿠폰 모델"""
    
    COUPON_TYPE_CHOICES = [
        ('CAR_WASH', '세차'),
        ('PRODUCT', '상품'),
        ('FUEL', '주유'),
    ]
    
    coupon_number = models.CharField(
        max_length=16, 
        unique=True, 
        verbose_name='쿠폰번호',
        help_text='16자리 쿠폰번호'
    )
    tid = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name='주유소 TID',
        help_text='쿠폰을 발행한 주유소 TID'
    )
    coupon_type = models.CharField(
        max_length=10,
        choices=COUPON_TYPE_CHOICES,
        verbose_name='쿠폰 종류',
        help_text='쿠폰의 종류 (세차, 상품, 주유)'
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name='쿠폰 사용 여부',
        help_text='쿠폰이 사용되었는지 여부'
    )
    customer_phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name='소유 고객 전화번호',
        help_text='쿠폰을 소유한 고객의 전화번호'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='쿠폰 생성일자',
        help_text='쿠폰이 생성된 날짜와 시간'
    )
    issued_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='쿠폰 발행일자',
        help_text='쿠폰이 고객에게 발행된 날짜와 시간'
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='쿠폰 사용일자',
        help_text='쿠폰이 사용된 날짜와 시간'
    )
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='발행 주유소',
        limit_choices_to={'user_type': 'STATION'},
        help_text='쿠폰을 발행한 주유소'
    )
    
    class Meta:
        verbose_name = '쿠폰'
        verbose_name_plural = '8. 쿠폰 목록'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['coupon_number']),
            models.Index(fields=['customer_phone']),
            models.Index(fields=['coupon_type']),
            models.Index(fields=['is_used']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        status = "사용됨" if self.is_used else "미사용"
        return f"{self.get_coupon_type_display()} 쿠폰 - {self.coupon_number} ({status})"
    
    def issue_to_customer(self, phone_number):
        """고객에게 쿠폰 발행"""
        if self.is_used:
            raise ValueError("이미 사용된 쿠폰입니다.")
        
        if self.issued_at:
            raise ValueError("이미 발행된 쿠폰입니다.")
        
        self.customer_phone = phone_number
        self.issued_at = timezone.now()
        self.save()
    
    def use_coupon(self):
        """쿠폰 사용"""
        if self.is_used:
            raise ValueError("이미 사용된 쿠폰입니다.")
        
        if not self.issued_at:
            raise ValueError("발행되지 않은 쿠폰입니다.")
        
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    @classmethod
    def generate_coupon_number(cls):
        """16자리 쿠폰번호 생성"""
        import random
        import string
        
        while True:
            # 16자리 랜덤 문자열 생성 (숫자 + 대문자)
            coupon_number = ''.join(random.choices(string.digits + string.ascii_uppercase, k=16))
            
            # 중복 확인
            if not cls.objects.filter(coupon_number=coupon_number).exists():
                return coupon_number
    
    @classmethod
    def create_coupon(cls, station, coupon_type, tid=None):
        """새로운 쿠폰 생성"""
        coupon_number = cls.generate_coupon_number()
        return cls.objects.create(
            coupon_number=coupon_number,
            station=station,
            coupon_type=coupon_type,
            tid=tid
        )
    
    def get_status_display(self):
        """쿠폰 상태 표시"""
        if self.is_used:
            return "사용됨"
        elif self.issued_at:
            return "발행됨"
        else:
            return "생성됨"
    
    @classmethod
    def get_available_coupons_for_station(cls, station):
        """특정 주유소의 사용 가능한 쿠폰 조회"""
        return cls.objects.filter(
            station=station,
            is_used=False,
            issued_at__isnull=True  # 아직 발행되지 않은 쿠폰
        ).order_by('coupon_type', 'created_at')
    
    @classmethod
    def get_coupon_counts_by_type(cls, station):
        """주유소별 쿠폰 종류별 개수 조회"""
        coupons = cls.get_available_coupons_for_station(station)
        counts = {
            'CAR_WASH': 0,
            'PRODUCT': 0,
            'FUEL': 0,
            'total': 0
        }
        
        for coupon in coupons:
            counts[coupon.coupon_type] += 1
            counts['total'] += 1
        
        return counts
