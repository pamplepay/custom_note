from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

CustomUser = get_user_model()

class CustomerVisitHistory(models.Model):
    """고객 방문 내역 모델"""
    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='visit_histories',
        limit_choices_to={'user_type': 'CUSTOMER'},
        verbose_name='고객'
    )
    station = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='customer_visits',
        limit_choices_to={'user_type': 'STATION'},
        verbose_name='주유소'
    )
    tid = models.CharField(max_length=20, blank=True, null=True, verbose_name='주유소 TID')
    visit_date = models.DateField(verbose_name='방문일')
    visit_time = models.TimeField(verbose_name='방문시간')
    payment_type = models.CharField(max_length=20, blank=True, null=True, verbose_name='결제구분')
    product_pack = models.CharField(max_length=50, blank=True, null=True, verbose_name='제품/PACK')
    sale_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='판매금액')
    fuel_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='주유량(L)')
    approval_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='승인번호')
    membership_card = models.CharField(max_length=500, blank=True, null=True, verbose_name='멤버십 카드번호')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')

    class Meta:
        verbose_name = '고객 방문 내역'
        verbose_name_plural = '고객 방문 내역'
        ordering = ['-visit_date', '-visit_time']
        unique_together = ['customer', 'station', 'visit_date', 'visit_time', 'approval_number']

    def __str__(self):
        return f"{self.customer.username} - {self.station.username} ({self.visit_date} {self.visit_time})" 