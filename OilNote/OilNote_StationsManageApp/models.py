from django.db import models
from OilNote_User.models import CustomUser

# Create your models here.

class StationBusinessInfo(models.Model):
    """주유소 사업자 정보 모델"""
    
    # 주유소와 사용자 연결
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='사용자')
    
    # 기본 정보
    business_code = models.CharField(max_length=20, unique=True, verbose_name='거래처 코드', default='000000')
    business_name = models.CharField(max_length=100, verbose_name='거래처명', default='')
    business_type = models.CharField(max_length=50, verbose_name='거래형태', default='외상')
    initial_balance = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='기초잔액', default=0)
    
    # 기존 필드들 (주유소 정보용)
    station_name = models.CharField(max_length=100, verbose_name='주유소명', blank=True, null=True)
    representative_name = models.CharField(max_length=50, verbose_name='대표자명', blank=True, null=True)
    business_registration_number = models.CharField(max_length=20, verbose_name='사업자등록번호', blank=True, null=True)
    sub_business_number = models.CharField(max_length=10, verbose_name='종사업자 번호', blank=True, null=True)
    
    # 주소 정보
    business_address = models.TextField(verbose_name='사업장 주소')
    
    # 사업 정보
    business_type = models.CharField(max_length=100, verbose_name='업태')
    business_category = models.CharField(max_length=100, verbose_name='종목')
    
    # 연락처
    phone_number = models.CharField(max_length=20, verbose_name='전화번호')
    
    # 석유 관련 정보
    refinery_company = models.CharField(max_length=50, verbose_name='정유사')
    petroleum_management_code = models.CharField(max_length=20, verbose_name='석유관리원 코드')
    oil_code = models.CharField(max_length=50, verbose_name='유개코드')
    
    # 생성/수정 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        db_table = 'OilNote_StationsManageApp_stationbusinessinfo'
        verbose_name = '주유소 사업자 정보'
        verbose_name_plural = '주유소 사업자 정보'
    
    def __str__(self):
        return f"{self.station_name} - {self.representative_name}"


class ProductInfo(models.Model):
    """유종 및 유외상품 정보 모델"""
    
    # 주유소와 사용자 연결
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='사용자')
    
    # 상품 정보
    item_code = models.CharField(max_length=20, unique=True, verbose_name='품목 코드')
    item_name = models.CharField(max_length=100, verbose_name='품목명')
    
    # 상품 분류 선택
    PRODUCT_CATEGORY_CHOICES = [
        ('일반유', '일반유'),
        ('TBA', 'TBA'),
        ('세차', '세차'),
        ('기타', '기타'),
    ]
    product_category = models.CharField(
        max_length=20, 
        choices=PRODUCT_CATEGORY_CHOICES, 
        verbose_name='상품 분류'
    )
    
    # 재고관리 여부
    INVENTORY_CHOICES = [
        ('예', '예'),
        ('아니오', '아니오'),
    ]
    inventory_management = models.CharField(
        max_length=10, 
        choices=INVENTORY_CHOICES, 
        default='예',
        verbose_name='재고관리여부'
    )
    
    # 기초재고수량
    initial_inventory_quantity = models.IntegerField(verbose_name='기초재고수량', default=0)
    
    # 생성/수정 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        db_table = 'OilNote_StationsManageApp_productinfo'
        verbose_name = '유종 및 유외상품 정보'
        verbose_name_plural = '유종 및 유외상품 정보'
        ordering = ['item_code']
    
    def __str__(self):
        return f"{self.item_code} - {self.item_name}"


class TankInfo(models.Model):
    """탱크 정보 모델"""
    
    # 주유소와 사용자 연결
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='사용자')
    
    # 탱크 정보
    tank_code = models.CharField(max_length=20, unique=True, verbose_name='탱크 코드')
    tank_number = models.CharField(max_length=10, verbose_name='탱크번호')
    
    # 품목(유종)명 선택
    FUEL_TYPE_CHOICES = [
        ('고급휘발유', '고급휘발유'),
        ('휘발유', '휘발유'),
        ('경유', '경유'),
        ('등유', '등유'),
        ('요소수', '요소수'),
        ('LPG', 'LPG'),
        ('기타', '기타'),
    ]
    fuel_type = models.CharField(
        max_length=20, 
        choices=FUEL_TYPE_CHOICES, 
        verbose_name='품목(유종)명'
    )
    
    # 허가 용량
    permitted_capacity = models.IntegerField(verbose_name='허가 용량(Ltr)')
    
    # 기초재고량
    initial_inventory = models.IntegerField(verbose_name='기초재고량(Ltr)', default=0)
    
    # 생성/수정 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        db_table = 'OilNote_StationsManageApp_tankinfo'
        verbose_name = '탱크 정보'
        verbose_name_plural = '탱크 정보'
        ordering = ['tank_code']
    
    def __str__(self):
        return f"{self.tank_code} - {self.fuel_type} (탱크 {self.tank_number})"


class NozzleInfo(models.Model):
    """주유기 노즐 정보 모델"""
    
    # 주유소와 사용자 연결
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='사용자')
    
    # 노즐 정보
    nozzle_code = models.CharField(max_length=20, unique=True, verbose_name='노즐 코드')
    nozzle_number = models.CharField(max_length=10, verbose_name='노즐 번호')
    
    # 연결된 탱크 정보
    connected_tank = models.ForeignKey(
        TankInfo, 
        on_delete=models.CASCADE, 
        verbose_name='연결탱크번호',
        related_name='nozzles'
    )
    
    # 품목(유종)명
    fuel_type = models.CharField(max_length=20, verbose_name='품목(유종)명')
    
    # 기초 계기자료
    initial_meter_data = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        verbose_name='기초 계기자료',
        default=0.000
    )
    
    # 생성/수정 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        db_table = 'OilNote_StationsManageApp_nozzleinfo'
        verbose_name = '주유기 노즐 정보'
        verbose_name_plural = '주유기 노즐 정보'
        ordering = ['nozzle_code']
    
    def __str__(self):
        return f"{self.nozzle_code} - {self.fuel_type} (노즐 {self.nozzle_number})"


class HomeloriVehicle(models.Model):
    """홈로리 차량 정보 모델"""
    
    # 주유소와 사용자 연결
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='사용자')
    
    # 차량 정보
    vehicle_code = models.CharField(max_length=20, unique=True, verbose_name='홈로리 차량 코드')
    vehicle_number = models.CharField(max_length=20, verbose_name='차량 번호')
    
    # 사용 유종 선택
    FUEL_TYPE_CHOICES = [
        ('고급휘발유', '고급휘발유'),
        ('휘발유', '휘발유'),
        ('경유', '경유'),
        ('등유', '등유'),
        ('요소수', '요소수'),
        ('LPG', 'LPG'),
        ('기타', '기타'),
    ]
    fuel_type = models.CharField(
        max_length=20, 
        choices=FUEL_TYPE_CHOICES, 
        verbose_name='사용 유종'
    )
    
    # 허가 용량
    permitted_capacity = models.IntegerField(verbose_name='허가 용량(Ltr)')
    
    # 생성/수정 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        db_table = 'OilNote_StationsManageApp_homelorivehicle'
        verbose_name = '홈로리 차량 정보'
        verbose_name_plural = '홈로리 차량 정보'
        ordering = ['vehicle_code']
    
    def __str__(self):
        return f"{self.vehicle_code} - {self.vehicle_number} ({self.fuel_type})"


class PaymentType(models.Model):
    """결제 형태 정보 모델"""
    
    # 주유소와 사용자 연결
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='사용자')
    
    # 결제 형태 정보
    code_number = models.CharField(max_length=20, unique=True, verbose_name='코드 번호')
    payment_type_name = models.CharField(max_length=100, verbose_name='결제 형태명')
    
    # 생성/수정 시간
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    
    class Meta:
        db_table = 'OilNote_StationsManageApp_paymenttype'
        verbose_name = '결제 형태 정보'
        verbose_name_plural = '결제 형태 정보'
        ordering = ['code_number']
    
    def __str__(self):
        return f"{self.code_number} - {self.payment_type_name}"
