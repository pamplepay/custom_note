from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from Cust_User.models import CustomUser, CustomerStationRelation
from django.conf import settings

# Create your models here.

class PointCard(models.Model):
    number = models.CharField(max_length=16, unique=True, verbose_name='카드번호')
    is_used = models.BooleanField(default=False, verbose_name='사용 여부')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='등록일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    
    # 카드를 등록한 주유소들
    stations = models.ManyToManyField(
        'Cust_User.CustomUser',
        through='StationCardMapping',
        related_name='registered_cards',
        limit_choices_to={'user_type': 'STATION'},
        verbose_name='등록 주유소'
    )

    class Meta:
        verbose_name = '포인트카드'
        verbose_name_plural = '포인트카드'
        ordering = ['-created_at']

    def __str__(self):
        return f"카드 {self.number} ({'사용중' if self.is_used else '미사용'})"
    
    def save(self, *args, **kwargs):
        if not self.pk:  # 새로운 카드 생성 시
            # 카드 번호가 16자리 숫자인지 검증
            if len(self.number) != 16:
                raise ValueError("카드 번호는 16자리여야 합니다.")
            
            if not self.number.isdigit():
                raise ValueError("카드 번호는 숫자로만 구성되어야 합니다.")
        
        super().save(*args, **kwargs)
    
    @property
    def oil_company_code(self):
        """정유사 코드 반환"""
        return self.number[0] if len(self.number) >= 1 else None
    
    @property
    def agency_code(self):
        """대리점 코드 반환"""
        return self.number[1:4] if len(self.number) >= 4 else None
    
    @property
    def station_code(self):
        """주유소 코드 반환"""
        return self.number[4:] if len(self.number) >= 16 else None

class StationCardMapping(models.Model):
    station = models.ForeignKey(
        'Cust_User.CustomUser', 
        on_delete=models.CASCADE, 
        limit_choices_to={'user_type': 'STATION'},
        verbose_name='주유소'
    )
    card = models.ForeignKey(
        PointCard, 
        on_delete=models.CASCADE,
        verbose_name='포인트카드'
    )
    registered_at = models.DateTimeField(default=timezone.now, verbose_name='등록일')
    is_active = models.BooleanField(default=True, verbose_name='활성화 여부')

    class Meta:
        verbose_name = '주유소-카드 매핑'
        verbose_name_plural = '주유소-카드 매핑'
        unique_together = ('station', 'card')
        ordering = ['-registered_at']

    def __str__(self):
        station_name = self.station.station_profile.station_name if hasattr(self.station, 'station_profile') else self.station.username
        return f"{station_name}의 카드 {self.card.number}"

class StationList(get_user_model()):
    class Meta:
        proxy = True
        verbose_name = '주유소'
        verbose_name_plural = '주유소 목록'

    def __str__(self):
        return self.username if hasattr(self, 'username') else str(self.id)

class PointHistory(models.Model):
    """포인트 변경 내역"""
    customer_station_relation = models.ForeignKey(
        CustomerStationRelation,
        on_delete=models.CASCADE,
        related_name='point_history',
        verbose_name='고객-주유소 관계'
    )
    points = models.IntegerField(verbose_name='포인트 변경')
    type = models.CharField(
        max_length=10,
        choices=[
            ('적립', '적립'),
            ('사용', '사용'),
            ('수정', '수정'),
            ('차감', '차감')
        ],
        verbose_name='변경 유형'
    )
    reason = models.CharField(max_length=200, verbose_name='변경 사유')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        verbose_name = '포인트 내역'
        verbose_name_plural = '포인트 내역'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer_station_relation} - {self.type} {self.points}점 ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

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
