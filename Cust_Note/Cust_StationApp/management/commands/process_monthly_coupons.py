"""
전월매출 기준 쿠폰 자동 발행 배치 작업

매월 1일에 실행되어 전월 매출 기준으로 쿠폰을 발행합니다.
크론탭 설정 예시:
0 1 1 * * /path/to/python /path/to/manage.py process_monthly_coupons
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from Cust_StationApp.models import (
    MonthlySalesStatistics, 
    CouponTemplate, 
    CustomerCoupon,
    CouponType
)
from Cust_User.models import CustomUser
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
        
        # 전월매출 쿠폰 템플릿 조회
        monthly_templates = CouponTemplate.objects.filter(
            station=station,
            coupon_type__type_code='MONTHLY',
            is_active=True
        )
        
        if not monthly_templates.exists():
            logger.info(f'주유소 {station.username}에 전월매출 쿠폰 템플릿이 없음')
            return 0, 0
        
        # 해당 월의 매출 통계 조회
        monthly_stats = MonthlySalesStatistics.objects.filter(
            tid__isnull=False,
            year_month=year_month
        )
        
        if not monthly_stats.exists():
            logger.info(f'{year_month}의 매출 통계 데이터가 없음')
            return 0, 0
        
        # 주유소의 TID별 매출 데이터 수집
        station_tids = self.get_station_tids(station)
        station_sales = monthly_stats.filter(tid__in=station_tids)
        
        if not station_sales.exists():
            logger.info(f'주유소 {station.username}의 {year_month} 매출 데이터가 없음')
            return 0, 0
        
        # 매출 기준 고객 선별 및 쿠폰 발행
        issued_count = 0
        customer_count = 0
        
        for template in monthly_templates:
            if not template.is_valid_today():
                continue
            
            # 템플릿별 발행 조건 확인 (예: 최소 매출 금액)
            threshold_amount = getattr(template, 'monthly_threshold', 50000)  # 기본 5만원
            
            # 해당 월에 임계값 이상 매출을 올린 고객들 찾기
            eligible_customers = self.find_eligible_customers(
                station, 
                year_month, 
                threshold_amount
            )
            
            logger.info(f'템플릿 {template.coupon_name}: {len(eligible_customers)}명 대상')
            
            for customer in eligible_customers:
                if not dry_run:
                    # 중복 발행 방지 체크
                    existing_coupon = CustomerCoupon.objects.filter(
                        customer=customer,
                        coupon_template=template,
                        issued_date__year=datetime.now().year,
                        issued_date__month=datetime.now().month
                    ).exists()
                    
                    if existing_coupon:
                        logger.info(f'고객 {customer.username}에게 이미 발행된 전월매출 쿠폰 존재')
                        continue
                    
                    # 쿠폰 발행
                    with transaction.atomic():
                        new_coupon = CustomerCoupon.objects.create(
                            customer=customer,
                            coupon_template=template,
                            status='AVAILABLE'
                        )
                        issued_count += 1
                        logger.info(f'✅ 전월매출 쿠폰 발행: {customer.username} → {template.coupon_name}')
                else:
                    issued_count += 1
                
                customer_count += 1
        
        return issued_count, customer_count
    
    def get_station_tids(self, station):
        """주유소의 TID 목록 조회"""
        tids = []
        
        # StationProfile에서 TID 조회
        if hasattr(station, 'station_profile') and station.station_profile.tid:
            tids.append(station.station_profile.tid)
        
        # 추가적인 TID 조회 로직 (카드 매핑 등에서)
        # 여기에 필요에 따라 추가 로직 구현
        
        return tids if tids else ['UNKNOWN']
    
    def find_eligible_customers(self, station, year_month, threshold_amount):
        """전월매출 쿠폰 발행 대상 고객 조회"""
        # 실제 구현에서는 매출 데이터와 고객 정보를 연결하여
        # 임계값 이상 매출을 올린 고객들을 찾아야 합니다.
        # 여기서는 예시로 해당 주유소의 고객들 중 일부를 반환합니다.
        
        from Cust_User.models import CustomerStationRelation
        
        # 해당 주유소의 고객들 조회
        relations = CustomerStationRelation.objects.filter(
            station=station,
            is_active=True
        )
        
        eligible_customers = []
        for relation in relations:
            # 실제로는 매출 데이터를 기반으로 판단해야 합니다.
            # 여기서는 예시로 모든 고객을 대상으로 합니다.
            eligible_customers.append(relation.customer)
        
        return eligible_customers