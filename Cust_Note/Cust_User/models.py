from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('CUSTOMER', '일반 고객'),
        ('STATION', '주유소'),
    )
    
    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='CUSTOMER',
        verbose_name='사용자 유형'
    )
    # phone_number = models.CharField(max_length=15, verbose_name='전화번호')  # 기본 전화번호 필드 주석 처리
    pw_back = models.CharField(max_length=128, blank=True, null=True, verbose_name='백업 패스워드')
    
    # 주유소 관련 필드
    station_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='주유소명')
    station_address = models.CharField(max_length=200, blank=True, null=True, verbose_name='주유소 주소')
    business_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='사업자 번호')
    
    # 일반 고객 관련 필드
    car_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='차량 번호')

    class Meta:
        verbose_name = '사용자'
        verbose_name_plural = '1. 사용자들'

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    @property
    def is_customer(self):
        return self.user_type == 'CUSTOMER'
    
    @property
    def is_station(self):
        return self.user_type == 'STATION'


class CustomerProfile(models.Model):
    """고객 전용 프로필"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='customer_profile')
    name = models.CharField(max_length=50, verbose_name='이름', blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    car_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='차량 번호')
    car_model = models.CharField(max_length=50, blank=True, null=True, verbose_name='차량 모델')
    membership_card = models.CharField(max_length=500, blank=True, null=True, verbose_name='멤버십 카드 번호')
    fuel_type = models.CharField(
        max_length=20, 
        choices=[
            ('GASOLINE', '휘발유'),
            ('DIESEL', '경유'),
            ('LPG', 'LPG'),
            ('ELECTRIC', '전기'),
            ('HYBRID', '하이브리드')
        ],
        blank=True, 
        null=True, 
        verbose_name='연료 타입'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='가입일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    class Meta:
        verbose_name = '고객 프로필'
        verbose_name_plural = '4. 고객 프로필들'

    def __str__(self):
        return f"{self.name or self.user.username}의 고객 프로필"

    def save(self, *args, **kwargs):
        if not self.pk:  # 새로운 프로필 생성 시에만
            if not self.name and self.user.first_name:
                self.name = self.user.first_name
        super().save(*args, **kwargs)


class StationProfile(models.Model):
    """주유소 전용 프로필"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='station_profile')
    business_number = models.CharField(max_length=10, unique=True, verbose_name='사업자등록번호')
    station_name = models.CharField(max_length=100, verbose_name='주유소명')
    address = models.CharField(max_length=200, verbose_name='주소', default='', blank=True)
    phone = models.CharField(max_length=20, verbose_name='전화번호', default='', blank=True)
    tid = models.CharField(max_length=20, verbose_name='단말기 번호(TID)', help_text='카드 결제 단말기 번호를 입력하세요', blank=True, null=True)
    
    # 주유소 코드 체계
    oil_company_code = models.CharField(max_length=1, verbose_name='정유사코드', default='0')
    agency_code = models.CharField(max_length=3, verbose_name='대리점코드', default='000')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='등록일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    class Meta:
        verbose_name = '주유소 프로필'
        verbose_name_plural = '주유소 프로필'

    def __str__(self):
        return f"{self.station_name} ({self.business_number})"
        
    def get_full_station_code(self):
        """전체 주유소 코드 반환 (정유사+대리점)"""
        return f"{self.oil_company_code}{self.agency_code}"


class CustomerStationRelation(models.Model):
    """고객과 주유소 연결 관계"""
    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='station_relations',
        limit_choices_to={'user_type': 'CUSTOMER'},
        verbose_name='고객'
    )
    station = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='customer_relations',
        limit_choices_to={'user_type': 'STATION'},
        verbose_name='주유소'
    )
    is_primary = models.BooleanField(default=False, verbose_name='주거래 여부')
    is_active = models.BooleanField(default=True, verbose_name='활성화 여부')
    points = models.PositiveIntegerField(default=0, verbose_name='포인트')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='등록일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    class Meta:
        verbose_name = '고객-주유소 관계'
        verbose_name_plural = '고객-주유소 관계'
        unique_together = ('customer', 'station')

    def __str__(self):
        return f"{self.customer.username} - {self.station.username} ({self.points}점)"

    def save(self, *args, **kwargs):
        # 주 거래처로 설정되면 다른 주 거래처는 해제
        if self.is_primary:
            type(self).objects.filter(
                customer=self.customer,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def record_visit(self):
        """방문 기록 갱신"""
        self.last_visit_date = timezone.now()
        self.visit_count += 1
        self.save()
