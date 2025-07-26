"""
전월매출 기준 쿠폰 자동 발행 배치 작업

매월 1일에 실행되어 전월 매출 기준으로 쿠폰을 발행합니다.
크론탭 설정 예시:
0 1 1 * * /path/to/python /path/to/manage.py process_monthly_coupons
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from datetime import datetime, timedelta
from Cust_StationApp.models import (
    ExcelSalesData,
    AutoCouponTemplate,
    CustomerCoupon
)
from Cust_User.models import CustomUser, StationProfile, CustomerStationRelation
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '전월매출 기준 쿠폰 자동 발행'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--year-month',
            type=str,
            help='처리할 년월 (YYYY-MM 형식, 기본값: 전월)'
        )
        parser.add_argument(
            '--station-id',
            type=int,
            help='특정 주유소만 처리 (선택사항)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 발행하지 않고 시뮬레이션만 실행'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== 전월매출 쿠폰 자동발행 배치 시작 ===')
        )
        
        # 처리할 년월 결정
        if options['year_month']:
            year_month = options['year_month']
            try:
                datetime.strptime(year_month, '%Y-%m')
            except ValueError:
                raise CommandError('년월 형식이 올바르지 않습니다. YYYY-MM 형식으로 입력해주세요.')
        else:
            # 전월 계산
            today = timezone.now().date()
            if today.month == 1:
                last_month = today.replace(year=today.year-1, month=12)
            else:
                last_month = today.replace(month=today.month-1)
            year_month = last_month.strftime('%Y-%m')
        
        self.stdout.write(f'처리 대상 년월: {year_month}')
        
        # 주유소 목록 조회
        stations = CustomUser.objects.filter(user_type='STATION')
        if options['station_id']:
            stations = stations.filter(id=options['station_id'])
        
        self.stdout.write(f'처리 대상 주유소: {stations.count()}개')
        
        total_issued = 0
        total_customers = 0
        
        for station in stations:
            try:
                issued_count, customer_count = self.process_monthly_coupons_for_station(
                    station, 
                    year_month, 
                    options['dry_run']
                )
                total_issued += issued_count
                total_customers += customer_count
                
                self.stdout.write(
                    f'✅ {station.username}: {customer_count}명 고객, {issued_count}개 쿠폰 발행'
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ {station.username} 처리 중 오류: {str(e)}')
                )
                logger.error(f'전월매출 쿠폰 처리 오류 - 주유소: {station.username}, 오류: {str(e)}', exc_info=True)
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'🔍 시뮬레이션 완료: {total_customers}명에게 {total_issued}개 쿠폰 발행 예정')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'🎉 배치 완료: {total_customers}명에게 {total_issued}개 쿠폰 발행')
            )
    
    def process_monthly_coupons_for_station(self, station, year_month, dry_run=False):
        """특정 주유소의 전월매출 쿠폰 처리"""
        logger.info(f'주유소 {station.username}의 {year_month} 전월매출 쿠폰 처리 시작')
        
        # 전월매출 쿠폰 템플릿 조회 (최신 1개만)
        monthly_template = AutoCouponTemplate.objects.filter(
            station=station,
            coupon_type='MONTHLY',
            is_active=True
        ).order_by('-created_at').first()
        
        if not monthly_template:
            logger.info(f'주유소 {station.username}에 전월매출 쿠폰 템플릿이 없음')
            return 0, 0
        
        # 주유소의 StationProfile에서 TID 가져오기
        try:
            station_profile = StationProfile.objects.get(user=station)
            tid = station_profile.tid
        except StationProfile.DoesNotExist:
            logger.error(f'주유소 {station.username}의 StationProfile이 없음')
            return 0, 0
        
        # 매출 기준 고객 선별 및 쿠폰 발행
        issued_count = 0
        customer_count = 0
        
        # 템플릿별 발행 조건 확인 (condition_data에서 threshold_amount 가져오기)
        threshold_amount = monthly_template.condition_data.get('threshold_amount', 50000)  # 기본 5만원
        logger.info(f'전월매출 쿠폰 임계값: {threshold_amount:,.0f}원')
        
        # 해당 월에 임계값 이상 매출을 올린 고객들 찾기
        eligible_customers = self.find_eligible_customers(
            station, 
            tid,
            year_month, 
            threshold_amount
        )
        
        logger.info(f'템플릿 {monthly_template.coupon_name}: {len(eligible_customers)}명 대상')
        
        for customer_data in eligible_customers:
            customer = customer_data['customer']
            sales_amount = customer_data['sales_amount']
            
            if not dry_run:
                # 이번 달에 이미 전월매출 쿠폰을 받았는지 체크
                # issued_date의 년월로 중복 체크
                current_year = datetime.now().year
                current_month = datetime.now().month
                existing_coupon = CustomerCoupon.objects.filter(
                    customer=customer,
                    auto_coupon_template=monthly_template,
                    issued_date__year=current_year,
                    issued_date__month=current_month
                ).exists()
                
                if existing_coupon:
                    logger.info(f'고객 {customer.username}에게 {year_month} 전월매출 쿠폰 이미 발행됨')
                    continue
                
                # 쿠폰 발행
                try:
                    with transaction.atomic():
                        # CustomerCoupon 직접 생성
                        new_coupon = CustomerCoupon.objects.create(
                            customer=customer,
                            auto_coupon_template=monthly_template,
                            status='AVAILABLE'
                        )
                        issued_count += 1
                        logger.info(f'✅ 전월매출 쿠폰 발행: {customer.username} → {monthly_template.coupon_name} (매출: {sales_amount:,.0f}원)')
                except Exception as e:
                    logger.error(f'쿠폰 발행 실패 - {customer.username}: {str(e)}')
            else:
                issued_count += 1
                logger.info(f'[DRY-RUN] {customer.username} → {monthly_template.coupon_name} (매출: {sales_amount:,.0f}원)')
            
            customer_count += 1
        
        return issued_count, customer_count
    
    def find_eligible_customers(self, station, tid, year_month, threshold_amount):
        """전월매출 쿠폰 발행 대상 고객 조회"""
        logger.info(f'전월매출 쿠폰 발행 대상 고객 조회 시작: {year_month}, 임계값: {threshold_amount:,.0f}원')
        
        # 년월에서 시작일과 종료일 계산
        year, month = map(int, year_month.split('-'))
        first_day = datetime(year, month, 1).date()
        
        # 다음 달의 첫날을 구하고 하루를 빼서 마지막 날 계산
        if month == 12:
            last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        logger.info(f'조회 기간: {first_day} ~ {last_day}')
        
        # ExcelSalesData에서 해당 월의 고객별 매출 합계 조회
        customer_sales = ExcelSalesData.objects.filter(
            tid=tid,
            sale_date__gte=first_day,
            sale_date__lte=last_day
        ).values('customer_name').annotate(
            total_amount=Sum('total_amount')
        ).filter(
            total_amount__gte=threshold_amount
        )
        
        logger.info(f'임계값 이상 매출 고객 수: {customer_sales.count()}명')
        
        eligible_customers = []
        
        for sale_data in customer_sales:
            customer_name = sale_data['customer_name']
            total_amount = sale_data['total_amount']
            
            # customer_name으로 실제 Customer 객체 찾기
            try:
                customer = CustomUser.objects.get(
                    username=customer_name,
                    user_type='CUSTOMER'
                )
                
                # 해당 고객이 이 주유소와 관계가 있는지 확인
                if CustomerStationRelation.objects.filter(
                    customer=customer,
                    station=station,
                    is_active=True
                ).exists():
                    eligible_customers.append({
                        'customer': customer,
                        'sales_amount': total_amount
                    })
                    logger.info(f'발행 대상: {customer_name} - 매출: {total_amount:,.0f}원')
                
            except CustomUser.DoesNotExist:
                logger.warning(f'고객 {customer_name}을 찾을 수 없음')
                continue
        
        return eligible_customers