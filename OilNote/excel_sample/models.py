from django.db import models

# Create your models here.

class ExcelData(models.Model):
    """엑셀 데이터 저장 모델"""
    name = models.CharField(max_length=100, verbose_name='이름')
    phone = models.CharField(max_length=20, verbose_name='전화번호')
    email = models.EmailField(verbose_name='이메일')
    address = models.CharField(max_length=200, verbose_name='주소')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='등록일')

    class Meta:
        verbose_name = '엑셀 데이터'
        verbose_name_plural = '엑셀 데이터 목록'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.email})"

class SalesData(models.Model):
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

    class Meta:
        verbose_name = '판매 데이터'
        verbose_name_plural = '판매 데이터'

    def __str__(self):
        return f"{self.sale_date} - {self.product_pack} - {self.total_amount}원"
