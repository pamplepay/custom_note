from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from Cust_User.models import CustomUser, CustomerStationRelation
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
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
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'},
        related_name='card_mappings',
        null=True,  # 기존 데이터 호환을 위해 null 허용
        blank=True
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
    car_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='차량 번호',
        help_text='고객의 차량 번호 (선택사항)'
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
        car_info = f" - {self.car_number}" if self.car_number else ""
        return f"{self.phone_number} - {self.membership_card.full_number}{car_info} ({status})"

    def clean(self):
        """데이터 검증"""
        from django.core.exceptions import ValidationError
        
        # 폰번호 형식 정리 (하이픈 제거)
        if self.phone_number:
            self.phone_number = self.phone_number.replace('-', '').replace(' ', '')
        
        # 차량 번호 정리 (빈 문자열이면 None으로 설정)
        if self.car_number:
            self.car_number = self.car_number.strip()
            if self.car_number == '':
                self.car_number = None
        
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
            
            # 차량 번호가 있으면 고객 프로필에 복사 (기존 차량번호가 없을 때만)
            if self.car_number and not user.customer_profile.car_number:
                user.customer_profile.car_number = self.car_number
            
            user.customer_profile.save()
        
        # 주유소와 고객 관계 생성
        from Cust_User.models import CustomerStationRelation
        relation, created = CustomerStationRelation.objects.get_or_create(
            customer=user,
            station=self.station,
            defaults={'is_active': True}
        )
        
        # 새로운 관계가 생성된 경우 회원가입 쿠폰 자동 발행
        if created:
            logger.info(f"🎯 새로운 고객-주유소 관계 생성됨, 회원가입 쿠폰 자동발행 시작")
            issued_count = auto_issue_signup_coupons(user, self.station)
            if issued_count > 0:
                logger.info(f"🎉 회원가입 쿠폰 {issued_count}개 자동 발행됨")
            else:
                logger.info(f"❌ 회원가입 쿠폰 발행되지 않음")
        else:
            logger.info(f"이미 존재하는 고객-주유소 관계, 회원가입 쿠폰 발행 건너뜀")
        
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
    is_cumulative_processed = models.BooleanField(default=False, verbose_name='누적매출 처리 완료', help_text='누적매출 추적 처리 여부')

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


# ========== 쿠폰 시스템 모델들 ==========

class CouponType(models.Model):
    """쿠폰 유형 모델 - 기본 6개 유형 + 사용자 정의 유형"""
    BASIC_TYPES = [
        ('SIGNUP', '회원가입'),
        ('CARWASH', '세차'),
        ('PRODUCT', '상품'),
        ('FUEL', '주유'),
        ('CUMULATIVE', '누적매출'),
        ('MONTHLY', '전월매출'),
    ]
    
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'}
    )
    type_code = models.CharField(
        max_length=20, 
        verbose_name='유형 코드',
        help_text="기본 유형(SIGNUP, CARWASH, PRODUCT, FUEL) 또는 사용자 정의 코드"
    )
    type_name = models.CharField(
        max_length=50, 
        verbose_name='유형명',
        help_text="쿠폰 유형의 표시명"
    )
    is_default = models.BooleanField(
        default=False, 
        verbose_name='기본 유형 여부',
        help_text="기본 4개 유형인지 사용자 정의 유형인지 구분"
    )
    is_active = models.BooleanField(default=True, verbose_name='활성화 여부')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    
    class Meta:
        verbose_name = '쿠폰 유형'
        verbose_name_plural = '8. 쿠폰 유형 목록'
        ordering = ['is_default', '-created_at']
        unique_together = ['station', 'type_code']
    
    def __str__(self):
        return f"{self.station.username} - {self.type_name}"


class CouponTemplate(models.Model):
    """쿠폰 템플릿 모델 - 주유소에서 생성하는 쿠폰 종류"""
    BENEFIT_TYPES = [
        ('DISCOUNT', '할인'),
        ('PRODUCT', '상품'),
        ('BOTH', '할인+상품'),
    ]
    
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'}
    )
    coupon_type = models.ForeignKey(
        CouponType, 
        on_delete=models.CASCADE, 
        verbose_name='쿠폰 유형'
    )
    coupon_name = models.CharField(
        max_length=100, 
        verbose_name='쿠폰명',
        help_text="고객에게 표시될 쿠폰 이름"
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='설명',
        help_text="쿠폰에 대한 상세 설명"
    )
    
    # 혜택 설정
    benefit_type = models.CharField(
        max_length=10, 
        choices=BENEFIT_TYPES, 
        verbose_name='혜택 유형'
    )
    
    # 할인 관련
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=0, 
        verbose_name='할인 금액',
        help_text="정액 할인 금액 (원)"
    )
    
    # 상품 관련
    product_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name='상품명',
        help_text="무료 제공할 상품명"
    )
    
    # 유효기간 설정
    is_permanent = models.BooleanField(
        default=False, 
        verbose_name='무기한 여부'
    )
    valid_from = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='사용 시작일'
    )
    valid_until = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='사용 종료일'
    )
    
    # 관리 필드
    is_active = models.BooleanField(default=True, verbose_name='활성화 여부')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        verbose_name = '쿠폰 템플릿'
        verbose_name_plural = '9. 쿠폰 템플릿 목록'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.station.username} - {self.coupon_name}"
    
    def is_valid_today(self):
        """오늘 날짜 기준으로 쿠폰이 유효한지 확인"""
        if self.is_permanent:
            return True
        
        today = timezone.now().date()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return True
    
    def get_benefit_description(self):
        """혜택 내용을 문자열로 반환"""
        if self.benefit_type == 'DISCOUNT':
            return f"{self.discount_amount:,.0f}원 할인"
        elif self.benefit_type == 'PRODUCT':
            return f"{self.product_name} 무료"
        elif self.benefit_type == 'BOTH':
            return f"{self.discount_amount:,.0f}원 할인 + {self.product_name} 무료"
        return ""


class CustomerCoupon(models.Model):
    """고객이 보유한 쿠폰"""
    STATUS_CHOICES = [
        ('AVAILABLE', '사용가능'),
        ('USED', '사용완료'),
        ('EXPIRED', '만료됨'),
    ]
    
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='고객',
        limit_choices_to={'user_type': 'CUSTOMER'}
    )
    coupon_template = models.ForeignKey(
        CouponTemplate, 
        on_delete=models.CASCADE, 
        verbose_name='쿠폰 템플릿',
        null=True,
        blank=True
    )
    auto_coupon_template = models.ForeignKey(
        'AutoCouponTemplate', 
        on_delete=models.CASCADE, 
        verbose_name='자동 쿠폰 템플릿',
        null=True,
        blank=True
    )
    
    # 쿠폰 상태
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='AVAILABLE', 
        verbose_name='사용 상태'
    )
    
    # 발행 및 사용 정보
    issued_date = models.DateTimeField(auto_now_add=True, verbose_name='발행일시')
    used_date = models.DateTimeField(null=True, blank=True, verbose_name='사용일시')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='만료일')
    
    # 사용 관련 정보
    used_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        null=True, 
        blank=True, 
        verbose_name='사용 금액',
        help_text="쿠폰 사용 시 거래 금액"
    )
    
    
    class Meta:
        verbose_name = '고객 쿠폰'
        verbose_name_plural = '10. 고객 쿠폰 목록'
        ordering = ['-issued_date']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['coupon_template']),
            models.Index(fields=['auto_coupon_template']),
        ]
    
    def __str__(self):
        template = self.auto_coupon_template or self.coupon_template
        return f"{self.customer.username} - {template.coupon_name} ({self.get_status_display()})"
    
    @property
    def template(self):
        """현재 쿠폰의 템플릿 반환 (auto_coupon_template 우선)"""
        return self.auto_coupon_template or self.coupon_template
    
    def save(self, *args, **kwargs):
        # 템플릿 유효성 검사
        if not self.auto_coupon_template and not self.coupon_template:
            raise ValueError("auto_coupon_template 또는 coupon_template 중 하나는 반드시 설정되어야 합니다.")
        
        template = self.template
        
        # 만료일 자동 설정
        if not self.expiry_date and not template.is_permanent:
            if template.valid_until:
                self.expiry_date = template.valid_until
        
        # 만료된 쿠폰 상태 자동 업데이트
        if self.expiry_date and timezone.now().date() > self.expiry_date:
            if self.status == 'AVAILABLE':
                self.status = 'EXPIRED'
        
        super().save(*args, **kwargs)
    
    def use_coupon(self, used_amount=None):
        """쿠폰 사용 처리"""
        if self.status != 'AVAILABLE':
            raise ValueError("사용할 수 없는 쿠폰입니다.")
        
        if self.expiry_date and timezone.now().date() > self.expiry_date:
            raise ValueError("만료된 쿠폰입니다.")
        
        self.status = 'USED'
        self.used_date = timezone.now()
        if used_amount:
            self.used_amount = used_amount
        self.save()
    
    def is_available(self):
        """쿠폰 사용 가능 여부 확인"""
        if self.status != 'AVAILABLE':
            return False
        
        if self.expiry_date and timezone.now().date() > self.expiry_date:
            return False
        
        return True


# ========== 새로운 쿠폰 시스템 모델들 ==========

class StationCouponQuota(models.Model):
    """주유소 쿠폰 수량 관리 모델"""
    station = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'},
        related_name='coupon_quota'
    )
    total_quota = models.IntegerField(default=0, verbose_name='총 쿠폰 수량')
    used_quota = models.IntegerField(default=0, verbose_name='사용된 수량')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        verbose_name = '주유소 쿠폰 수량'
        verbose_name_plural = '11. 주유소 쿠폰 수량 관리'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.station.username} - 총:{self.total_quota} 사용:{self.used_quota} 잔여:{self.remaining_quota}"
    
    @property
    def remaining_quota(self):
        """남은 쿠폰 수량"""
        return max(0, self.total_quota - self.used_quota)
    
    def can_issue_coupons(self, count=1):
        """쿠폰 발행 가능 여부 확인"""
        return self.remaining_quota >= count
    
    def use_quota(self, count=1):
        """쿠폰 수량 사용"""
        if not self.can_issue_coupons(count):
            raise ValueError(f"쿠폰 수량 부족 (요청: {count}, 잔여: {self.remaining_quota})")
        
        self.used_quota += count
        self.save()
        return True


class CumulativeSalesTracker(models.Model):
    """누적매출 추적 모델"""
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='고객',
        limit_choices_to={'user_type': 'CUSTOMER'},
        related_name='cumulative_sales_as_customer'
    )
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'},
        related_name='cumulative_sales_as_station'
    )
    cumulative_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='누적 매출액'
    )
    threshold_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50000,
        verbose_name='쿠폰 발행 임계값'
    )
    last_coupon_issued_at = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='마지막 쿠폰 발행 시점의 누적액'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        verbose_name = '누적매출 추적'
        verbose_name_plural = '12. 누적매출 추적 목록'
        ordering = ['-updated_at']
        unique_together = ['customer', 'station']
    
    def __str__(self):
        return f"{self.customer.username}@{self.station.username} - 누적:{self.cumulative_amount:,.0f}원"
    
    def should_issue_coupon(self):
        """쿠폰 발행 조건 확인"""
        if self.cumulative_amount < self.threshold_amount:
            return False
        
        # 마지막 쿠폰 발행 이후 임계값 이상 추가 매출 발생 확인
        additional_sales = self.cumulative_amount - self.last_coupon_issued_at
        return additional_sales >= self.threshold_amount
    
    def get_coupon_count(self):
        """발행할 쿠폰 개수 계산"""
        if not self.should_issue_coupon():
            return 0
        
        additional_sales = self.cumulative_amount - self.last_coupon_issued_at
        return int(additional_sales // self.threshold_amount)
    
    def should_issue_coupon_improved(self):
        """개선된 쿠폰 발행 조건 확인 - 튜플 반환 (should_issue, coupon_count)"""
        if self.cumulative_amount < self.threshold_amount:
            return False, 0
        
        # 마지막 쿠폰 발행 이후 추가 매출 계산
        additional_sales = self.cumulative_amount - self.last_coupon_issued_at
        
        if additional_sales < self.threshold_amount:
            return False, 0
        
        # 발행할 쿠폰 개수 계산
        coupon_count = int(additional_sales // self.threshold_amount)
        
        return coupon_count > 0, coupon_count
    
    def update_threshold_from_template(self, station):
        """AutoCouponTemplate에서 임계값 업데이트"""
        auto_template = AutoCouponTemplate.objects.filter(
            station=station,
            coupon_type='CUMULATIVE',
            is_active=True
        ).first()
        
        if auto_template and 'threshold_amount' in auto_template.condition_data:
            new_threshold = auto_template.condition_data['threshold_amount']
            if new_threshold != self.threshold_amount:
                logger.info(f"임계값 업데이트: {self.threshold_amount:,.0f}원 → {new_threshold:,.0f}원")
                self.threshold_amount = new_threshold
                self.save()
                return True
        return False


class CouponPurchaseRequest(models.Model):
    """쿠폰 구매 요청 모델"""
    STATUS_CHOICES = [
        ('PENDING', '대기'),
        ('APPROVED', '승인'),
        ('REJECTED', '거부'),
    ]
    
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'}
    )
    requested_quantity = models.IntegerField(verbose_name='요청 수량')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='처리 상태'
    )
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='요청일시')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='처리일시')
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_coupon_requests',
        verbose_name='처리자'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='비고')
    
    class Meta:
        verbose_name = '쿠폰 구매 요청'
        verbose_name_plural = '13. 쿠폰 구매 요청 목록'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.station.username} - {self.requested_quantity}개 ({self.get_status_display()})"
    
    def approve(self, admin_user, notes=None):
        """구매 요청 승인"""
        from django.db import transaction
        from django.utils import timezone
        
        if self.status != 'PENDING':
            raise ValueError("이미 처리된 요청입니다.")
        
        with transaction.atomic():
            # 쿠폰 수량 증가
            quota, created = StationCouponQuota.objects.get_or_create(
                station=self.station,
                defaults={'total_quota': 0, 'used_quota': 0}
            )
            quota.total_quota += self.requested_quantity
            quota.save()
            
            # 요청 상태 업데이트
            self.status = 'APPROVED'
            self.processed_at = timezone.now()
            self.processed_by = admin_user
            if notes:
                self.notes = notes
            self.save()
    
    def reject(self, admin_user, notes=None):
        """구매 요청 거부"""
        from django.utils import timezone
        
        if self.status != 'PENDING':
            raise ValueError("이미 처리된 요청입니다.")
        
        self.status = 'REJECTED'
        self.processed_at = timezone.now()
        self.processed_by = admin_user
        if notes:
            self.notes = notes
        self.save()


class CustomerVisitHistory(models.Model):
    """고객 방문 기록 모델 (매출 데이터 연동용)"""
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='고객',
        limit_choices_to={'user_type': 'CUSTOMER'},
        related_name='visit_history_as_customer'
    )
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'},
        related_name='visit_history_as_station'
    )
    visit_date = models.DateTimeField(verbose_name='방문일시')
    fuel_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='주유량'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='결제 금액'
    )
    products = models.JSONField(default=list, verbose_name='구매 상품')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    
    class Meta:
        verbose_name = '고객 방문 기록'
        verbose_name_plural = '14. 고객 방문 기록'
        ordering = ['-visit_date']
    
    def __str__(self):
        return f"{self.customer.username}@{self.station.username} - {self.visit_date.strftime('%Y-%m-%d')} ({self.amount:,.0f}원)"


def auto_issue_signup_coupons(customer, station):
    """회원가입 쿠폰 자동 발행"""
    logger.info(f"=== 회원가입 쿠폰 자동발행 시작 ===")
    logger.info(f"고객: {customer.username} (ID: {customer.id})")
    logger.info(f"주유소: {station.username} (ID: {station.id})")
    
    try:
        # 해당 주유소의 회원가입 쿠폰 템플릿 조회 (최신 1개만)
        signup_template = AutoCouponTemplate.objects.filter(
            station=station,
            coupon_type='SIGNUP',
            is_active=True
        ).order_by('-created_at').first()
        
        logger.info(f"주유소 {station.username}의 회원가입 쿠폰 템플릿 조회 결과: {'1개' if signup_template else '0개'}")
        
        if not signup_template:
            logger.info("회원가입 쿠폰 템플릿이 존재하지 않음")
            return 0
        
        issued_count = 0
        template = signup_template
        logger.info(f"템플릿 처리 중: {template.coupon_name} (ID: {template.id})")
        
        # 템플릿 유효성 확인
        if not template.is_valid_today():
            logger.info(f"템플릿 {template.coupon_name}은 유효기간이 아님 (is_permanent: {template.is_permanent}, valid_from: {template.valid_from}, valid_until: {template.valid_until})")
            return 0
        
        logger.info(f"템플릿 {template.coupon_name}은 유효함")
        
        # 이미 발행된 회원가입 쿠폰이 있는지 확인 (중복 발행 방지)
        existing_coupon = CustomerCoupon.objects.filter(
            customer=customer,
            auto_coupon_template=template
        ).first()
        
        if existing_coupon:
            logger.info(f"이미 발행된 회원가입 쿠폰이 존재: {template.coupon_name} (쿠폰 ID: {existing_coupon.id})")
            return 0
        
        logger.info(f"새로운 회원가입 쿠폰 발행 중: {template.coupon_name}")
        
        # 회원가입 쿠폰 발행 (수량 제한 없음)
        new_coupon = CustomerCoupon.objects.create(
            customer=customer,
            auto_coupon_template=template,
            status='AVAILABLE'
        )
        
        issued_count += 1
        logger.info(f"✅ 회원가입 쿠폰 발행 완료: {template.coupon_name} (새 쿠폰 ID: {new_coupon.id})")
        
        if issued_count > 0:
            logger.info(f"🎉 총 {issued_count}개의 회원가입 쿠폰 발행 완료")
        else:
            logger.info("❌ 발행할 회원가입 쿠폰이 없음")
            
        logger.info(f"=== 회원가입 쿠폰 자동발행 종료 ===")
        return issued_count
        
    except Exception as e:
        logger.error(f"❌ 회원가입 쿠폰 자동발행 중 오류: {str(e)}", exc_info=True)
        return 0


def track_cumulative_sales(customer, station, sale_amount, excel_sales_data):
    """ExcelSalesData 기반 누적매출 추적 및 쿠폰 발행"""
    from django.db import transaction
    from django.db.models import Sum
    from Cust_User.models import StationProfile
    import time
    
    start_time = time.time()
    logger.info(f"=== ExcelSalesData 기반 누적매출 쿠폰 추적 시작 ===")
    logger.info(f"고객: {customer.username} (ID: {customer.id}), 주유소: {station.username} (ID: {station.id}), 매출: {sale_amount:,.0f}원")
    
    try:
        with transaction.atomic():
            # StationProfile에서 TID 가져오기
            station_profile = StationProfile.objects.filter(user=station).first()
            if not station_profile:
                logger.warning(f"주유소 {station.username}의 StationProfile을 찾을 수 없음")
                return
            
            # 이전 누적매출 계산 (현재 처리 중인 매출 제외)
            previous_sales = ExcelSalesData.objects.filter(
                customer_name=customer.username,
                tid=station_profile.tid,
                is_cumulative_processed=True
            ).exclude(id=excel_sales_data.id).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # 현재 매출 금액
            current_sale_amount = float(excel_sales_data.total_amount)
            
            # 새로운 전체 누적매출 (이전 매출 + 현재 매출)
            new_total_sales = float(previous_sales) + current_sale_amount
            
            logger.info(f"이전 누적매출: {previous_sales:,.0f}원")
            logger.info(f"현재 매출: {current_sale_amount:,.0f}원")
            logger.info(f"새로운 전체 누적매출: {new_total_sales:,.0f}원")
            
            # AutoCouponTemplate에서 임계값 가져오기
            auto_template = AutoCouponTemplate.objects.filter(
                station=station,
                coupon_type='CUMULATIVE',
                is_active=True
            ).first()
            
            if not auto_template:
                logger.warning(f"활성화된 누적매출 AutoCouponTemplate이 없음: {station.username}")
                return
            
            threshold_amount = auto_template.condition_data.get('threshold_amount', 50000)
            logger.info(f"누적매출 쿠폰 임계값: {threshold_amount:,.0f}원")
            
            # 이미 발행된 누적매출 쿠폰 개수 확인 (모든 템플릿 포함)
            # 템플릿 전환 시 중복 발행 방지를 위해 전체 누적매출 쿠폰 개수를 확인
            issued_coupons = CustomerCoupon.objects.filter(
                customer=customer,
                auto_coupon_template__station=station,
                auto_coupon_template__coupon_type='CUMULATIVE'
            ).count()
            
            # 이전 상태에서 발행되어야 했던 쿠폰 개수
            previous_should_have = int(float(previous_sales) // float(threshold_amount))
            
            # 새로운 전체 상태에서 발행되어야 할 쿠폰 개수
            new_should_have = int(float(new_total_sales) // float(threshold_amount))
            
            # 실제 추가 발행 필요한 쿠폰 개수
            new_coupons_needed = max(0, new_should_have - previous_should_have)
            
            logger.info(f"이전 발행되어야 할 쿠폰: {previous_should_have}개")
            logger.info(f"새로운 발행되어야 할 쿠폰: {new_should_have}개")
            logger.info(f"이미 발행된 쿠폰: {issued_coupons}개")
            logger.info(f"추가 발행 필요: {new_coupons_needed}개")
            
            if new_coupons_needed > 0:
                logger.info(f"누적매출 쿠폰 발행 시작: {new_coupons_needed}개")
                
                # 누적매출 쿠폰은 이미 계산된 조건으로 바로 발행
                if auto_template.is_valid_today():
                    # 벌크 생성을 위한 쿠폰 리스트
                    coupons_to_create = []
                    
                    for i in range(new_coupons_needed):
                        coupons_to_create.append(
                            CustomerCoupon(
                                customer=customer,
                                auto_coupon_template=auto_template,
                                status='AVAILABLE',
                            )
                        )
                    
                    # 벌크 생성으로 성능 개선
                    created_coupons = CustomerCoupon.objects.bulk_create(coupons_to_create)
                    issued_count = len(created_coupons)
                    
                    # 템플릿 통계 업데이트
                    auto_template.issued_count += issued_count
                    auto_template.total_issued += issued_count
                    auto_template.save()
                    
                    logger.info(f"✅ 누적매출 쿠폰 {issued_count}개 발행 완료: {auto_template.coupon_name}")
                    logger.info(f"발행 기준 누적액: {new_total_sales:,.0f}원")
                else:
                    logger.warning(f"쿠폰 발행 불가: {reason}")
            else:
                remaining = float(threshold_amount) - (float(new_total_sales) % float(threshold_amount))
                logger.info(f"누적매출 쿠폰 발행 조건 미충족 (다음 발행까지 {remaining:,.0f}원 필요)")
            
            elapsed_time = time.time() - start_time
            logger.info(f"=== ExcelSalesData 기반 누적매출 쿠폰 추적 종료 (소요시간: {elapsed_time:.3f}초) ===")
            
    except Exception as e:
        logger.error(f"❌ ExcelSalesData 기반 누적매출 쿠폰 추적 중 오류: {str(e)}", exc_info=True)
        raise  # 트랜잭션 롤백을 위해 예외 재발생


def should_issue_cumulative_coupon(tracker):
    """누적매출 쿠폰 발행 조건 확인"""
    return tracker.should_issue_coupon()


def issue_cumulative_coupon(tracker):
    """누적매출 쿠폰 발행"""
    coupon_count = tracker.get_coupon_count()
    
    if coupon_count <= 0:
        return 0
    
    # 누적매출 쿠폰 템플릿 조회
    cumulative_templates = CouponTemplate.objects.filter(
        station=tracker.station,
        coupon_type__type_code='CUMULATIVE',
        is_active=True
    )
    
    issued_count = 0
    for template in cumulative_templates:
        if template.is_valid_today():
            for _ in range(coupon_count):
                CustomerCoupon.objects.create(
                    customer=tracker.customer,
                    coupon_template=template,
                    status='AVAILABLE'
                )
                issued_count += 1
    
    # 마지막 쿠폰 발행 시점 업데이트
    tracker.last_coupon_issued_at = tracker.cumulative_amount
    tracker.save()
    
    return issued_count


# ========== 자동 쿠폰 CRUD 모델들 ==========

class AutoCouponTemplate(models.Model):
    """자동 쿠폰 템플릿 - CRUD 지원"""
    COUPON_TYPES = [
        ('SIGNUP', '회원가입'),
        ('CUMULATIVE', '누적매출'), 
        ('MONTHLY', '전월매출'),
    ]
    
    BENEFIT_TYPES = [
        ('DISCOUNT', '할인'),
        ('PRODUCT', '상품'),
        ('BOTH', '할인+상품'),
    ]
    
    # 기본 정보
    station = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='주유소',
        limit_choices_to={'user_type': 'STATION'}
    )
    coupon_type = models.CharField(
        max_length=20, 
        choices=COUPON_TYPES, 
        verbose_name='쿠폰 유형'
    )
    coupon_name = models.CharField(
        max_length=100, 
        verbose_name='쿠폰명',
        help_text="고객에게 표시될 쿠폰 이름"
    )
    description = models.TextField(
        blank=True, 
        verbose_name='설명',
        help_text="쿠폰에 대한 상세 설명"
    )
    
    # 혜택 설정
    benefit_type = models.CharField(
        max_length=10, 
        choices=BENEFIT_TYPES, 
        verbose_name='혜택 유형'
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=0, 
        verbose_name='할인 금액'
    )
    product_name = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name='상품명'
    )
    
    # 조건 설정 (JSON으로 복합 조건 저장)
    condition_data = models.JSONField(
        default=dict, 
        verbose_name='조건 데이터',
        help_text="발행 조건들을 JSON으로 저장"
    )
    
    # 관리 설정
    is_active = models.BooleanField(
        default=True, 
        verbose_name='활성 상태'
    )
    max_issue_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='최대 발행수',
        help_text="null이면 무제한 발행"
    )
    issued_count = models.IntegerField(
        default=0, 
        verbose_name='현재 발행수'
    )
    
    # 유효기간
    is_permanent = models.BooleanField(
        default=False, 
        verbose_name='무기한 여부'
    )
    valid_from = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='사용 시작일'
    )
    valid_until = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='사용 종료일'
    )
    
    # 통계 정보
    total_issued = models.IntegerField(
        default=0, 
        verbose_name='총 발행수'
    )
    total_used = models.IntegerField(
        default=0, 
        verbose_name='총 사용수'
    )
    
    # 메타 정보
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_auto_coupons',
        verbose_name='생성자'
    )
    
    class Meta:
        verbose_name = '자동 쿠폰 템플릿'
        verbose_name_plural = '15. 자동 쿠폰 템플릿 목록'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['station', 'coupon_type', 'is_active']),
        ]
    
    def __str__(self):
        status = "활성" if self.is_active else "비활성"
        return f"[{status}] {self.coupon_name} - {self.get_coupon_type_display()}"
    
    def is_valid_today(self):
        """오늘 날짜 기준으로 쿠폰이 유효한지 확인"""
        if self.is_permanent:
            return True
        
        today = timezone.now().date()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return True
    
    def can_issue_more(self):
        """더 발행할 수 있는지 확인"""
        if self.max_issue_count is None:
            return True  # 무제한 발행
        return self.issued_count < self.max_issue_count
    
    def get_remaining_count(self):
        """남은 발행 가능 수량"""
        if self.max_issue_count is None:
            return None  # 무제한
        return max(0, self.max_issue_count - self.issued_count)
    
    def get_issue_progress_rate(self):
        """발행 진행률 (%) - max_issue_count가 설정된 경우만"""
        if self.max_issue_count is None or self.max_issue_count == 0:
            return None
        return round(self.issued_count / self.max_issue_count * 100, 1)
    
    def is_already_issued_to_customer(self, customer):
        """해당 고객에게 이미 발행되었는지 확인"""
        # AutoCouponTemplate과 연결된 쿠폰 발행 이력 확인
        # (CustomerCoupon 모델에 auto_template 필드 추가 필요)
        return False  # 임시로 False 반환
    
    def can_issue_to_customer(self, customer):
        """고객에게 발행 가능한지 종합 체크"""
        # 활성 상태 확인
        if not self.is_active:
            return False, "비활성화된 템플릿"
        
        # 유효 기간 확인
        if not self.is_valid_today():
            return False, "유효 기간이 아님"
        
        # 최대 발행수 확인
        if not self.can_issue_more():
            return False, f"최대 발행수 도달 ({self.issued_count}/{self.max_issue_count})"
        
        # 중복 발행 확인 (필요 시)
        if self.is_already_issued_to_customer(customer):
            return False, "이미 발행된 고객"
        
        return True, "발행 가능"
    
    def issue_to_customer(self, customer):
        """고객에게 쿠폰 발행"""
        can_issue, reason = self.can_issue_to_customer(customer)
        if not can_issue:
            return False, reason
        
        try:
            # 기존 CouponTemplate과 호환되는 방식으로 쿠폰 발행
            # (구현은 이후 단계에서)
            
            # 발행 수 증가
            self.issued_count += 1
            self.total_issued += 1
            self.save(update_fields=['issued_count', 'total_issued'])
            
            logger.info(f"자동 쿠폰 발행 성공: {self.coupon_name} -> {customer.username}")
            return True, "발행 성공"
            
        except Exception as e:
            logger.error(f"자동 쿠폰 발행 오류: {e}")
            return False, f"발행 오류: {str(e)}"
    
    def get_usage_rate(self):
        """사용률 계산"""
        if self.total_issued == 0:
            return 0
        return round(self.total_used / self.total_issued * 100, 1)
    
    def get_benefit_description(self):
        """혜택 내용을 문자열로 반환"""
        if self.benefit_type == 'DISCOUNT':
            return f"{self.discount_amount:,.0f}원 할인"
        elif self.benefit_type == 'PRODUCT':
            return f"{self.product_name} 증정"
        elif self.benefit_type == 'BOTH':
            return f"{self.discount_amount:,.0f}원 할인 + {self.product_name} 증정"
        return "혜택 없음"


class AutoCouponCondition(models.Model):
    """자동 쿠폰 발행 조건 (고급 조건 관리)"""
    CONDITION_TYPES = [
        ('THRESHOLD_AMOUNT', '금액 임계값'),
        ('TIME_PERIOD', '기간 조건'),
        ('CUSTOMER_TYPE', '고객 유형'),
        ('EXCLUDE_PREVIOUS', '기존 수령자 제외'),
        ('VISIT_COUNT', '방문 횟수'),
        ('WEEKDAY_ONLY', '평일만'),
        ('WEEKEND_ONLY', '주말만'),
        ('CUSTOMER_GRADE', '고객 등급'),
    ]
    
    template = models.ForeignKey(
        AutoCouponTemplate,
        on_delete=models.CASCADE,
        related_name='conditions',
        verbose_name='자동 쿠폰 템플릿'
    )
    condition_type = models.CharField(
        max_length=20,
        choices=CONDITION_TYPES,
        verbose_name='조건 유형'
    )
    condition_value = models.JSONField(
        verbose_name='조건 값',
        help_text="조건별 설정값을 JSON으로 저장"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='활성 상태'
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='조건 설명'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    
    class Meta:
        verbose_name = '자동 쿠폰 조건'
        verbose_name_plural = '16. 자동 쿠폰 조건 목록'
        ordering = ['condition_type', 'created_at']
    
    def __str__(self):
        return f"{self.template.template_name} - {self.get_condition_type_display()}"
    
    def evaluate(self, customer):
        """고객에 대해 이 조건을 평가"""
        try:
            if self.condition_type == 'THRESHOLD_AMOUNT':
                threshold = self.condition_value.get('amount', 0)
                # 실제 평가 로직 구현
                return True
            
            
            # 다른 조건들도 구현
            return True
            
        except Exception as e:
            logger.error(f"조건 평가 오류: {e}")
            return False


# ========== Django 시그널 ==========

@receiver(post_save, sender=CustomerVisitHistory)
def on_customer_visit(sender, instance, created, **kwargs):
    """고객 방문 시 누적매출 추적"""
    if created and instance.fuel_quantity > 0:
        logger.info(f"고객 방문 감지, 누적매출 추적 시작: {instance.customer.username}@{instance.station.username}")
        track_cumulative_sales(instance.customer, instance.station, instance.sale_amount)


@receiver(post_save, sender=ExcelSalesData)
def on_excel_sales_data(sender, instance, created, **kwargs):
    """ExcelSalesData 생성 시 누적매출 추적 (보너스카드 없이도)"""
    # 중복 처리 방지: 이미 처리된 데이터는 건너뛰기
    if not created or instance.total_amount <= 0 or instance.is_cumulative_processed:
        return
        
    try:
        # customer_name으로 고객 찾기
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        customer = User.objects.filter(
            username=instance.customer_name,
            user_type='CUSTOMER'
        ).first()
        
        # TID로 주유소 찾기
        from Cust_User.models import StationProfile
        station_profile = StationProfile.objects.filter(tid=instance.tid).first()
        station = station_profile.user if station_profile else None
        
        if customer and station:
            logger.info(f"ExcelSalesData 기반 누적매출 추적: {customer.username}@{station.username} (금액: {instance.total_amount:,}원)")
            
            # 누적매출 추적 실행
            track_cumulative_sales(customer, station, instance.total_amount, instance)
            
            # 처리 완료 플래그 설정
            ExcelSalesData.objects.filter(id=instance.id).update(is_cumulative_processed=True)
            logger.info(f"ExcelSalesData ID {instance.id} 누적매출 처리 완료 플래그 설정")
            
        else:
            logger.warning(f"누적매출 추적 실패 - 사용자 찾기 실패: customer={instance.customer_name}, tid={instance.tid}")
            # 사용자를 찾지 못한 경우에도 플래그 설정하여 재시도 방지
            ExcelSalesData.objects.filter(id=instance.id).update(is_cumulative_processed=True)
            
    except Exception as e:
        logger.error(f"ExcelSalesData 누적매출 추적 중 오류 (ID: {instance.id}): {e}")
        # 오류 발생 시 추적을 위해 스택 트레이스도 기록
        import traceback
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        # 오류가 발생해도 플래그는 설정하지 않음 (재시도 가능하도록)
