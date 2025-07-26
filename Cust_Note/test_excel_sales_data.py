#!/usr/bin/env python
"""
엑셀 매출 데이터 테스트 생성 스크립트
- ExcelSalesData 생성
- SalesStatistics 자동 생성
- CustomerVisitHistory 생성 (보너스카드 매칭 시)
"""

import os
import sys
import django
from datetime import datetime, timedelta, time
from decimal import Decimal
import random

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from Cust_StationApp.models import ExcelSalesData, SalesStatistics
from Cust_UserApp.models import CustomerVisitHistory
from Cust_User.models import StationProfile, CustomerProfile

User = get_user_model()


class ExcelSalesDataGenerator:
    """엑셀 매출 데이터 생성기"""
    
    def __init__(self):
        self.products = ['휘발유', '경유', 'LPG', '등유']
        self.payment_types = ['현금', '카드', '포인트', '혼합']
        self.sale_types = ['일반', '할인', '이벤트']
        
    def generate_sales_data(self, customer_username, station_username, amount, 
                          sale_date=None, bonus_card=None, product=None, skip_bonus_card=True):
        """
        매출 데이터 생성
        
        Parameters:
        -----------
        customer_username : str
            고객 사용자명
        station_username : str
            주유소 사용자명
        amount : float
            판매 금액
        sale_date : datetime.date, optional
            판매 날짜 (기본값: 오늘)
        bonus_card : str, optional
            보너스카드 번호 (기본값: 고객의 membership_card)
        product : str, optional
            제품명 (기본값: 랜덤)
        
        Returns:
        --------
        dict : 생성된 데이터 정보
        """
        
        # 사용자 확인
        try:
            customer = User.objects.get(username=customer_username, user_type='CUSTOMER')
            station = User.objects.get(username=station_username, user_type='STATION')
        except User.DoesNotExist as e:
            print(f"❌ 사용자를 찾을 수 없습니다: {e}")
            return None
            
        # 주유소 TID 가져오기
        station_profile = StationProfile.objects.filter(user=station).first()
        tid = station_profile.tid if station_profile else f"TID_{station.id}"
        
        # 고객 프로필 및 보너스카드
        customer_profile = CustomerProfile.objects.filter(user=customer).first()
        if not skip_bonus_card and not bonus_card and customer_profile:
            bonus_card = customer_profile.membership_card or f"CARD_{customer.id}"
        elif skip_bonus_card:
            bonus_card = ""  # 보너스카드 없음
            
        # 기본값 설정
        if not sale_date:
            sale_date = datetime.now().date()
        if not product:
            product = random.choice(self.products)
            
        # 리터당 가격 (휘발유: 1400원, 경유: 1300원, LPG: 900원, 등유: 1200원)
        price_per_liter = {
            '휘발유': 1400,
            '경유': 1300,
            'LPG': 900,
            '등유': 1200
        }.get(product, 1400)
        
        # 수량 계산
        quantity = round(float(amount) / price_per_liter, 2)
        
        # 시간 랜덤 생성
        sale_time = time(
            hour=random.randint(6, 22),
            minute=random.randint(0, 59),
            second=random.randint(0, 59)
        )
        
        # 승인번호 생성
        approval_number = f"AP{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        print(f"\n📊 매출 데이터 생성 시작")
        print(f"   고객: {customer.username}")
        print(f"   주유소: {station.username} (TID: {tid})")
        print(f"   제품: {product}")
        print(f"   금액: {amount:,}원")
        print(f"   수량: {quantity}L")
        print(f"   날짜: {sale_date}")
        print(f"   보너스카드: {bonus_card}")
        
        # 1. ExcelSalesData 생성
        excel_data = self._create_excel_sales_data(
            tid, sale_date, sale_time, customer, product, 
            quantity, price_per_liter, amount, approval_number, 
            bonus_card
        )
        
        # 2. SalesStatistics 생성/업데이트
        sales_stat = self._update_sales_statistics(tid, sale_date)
        
        # 3. 누적매출 추적은 Django Signal에서 자동 처리됨
        print(f"🎯 누적매출 추적은 Django Signal로 자동 처리: {amount:,}원")
        
        # 4. CustomerVisitHistory 생성 (보너스카드가 있는 경우)
        visit_history = None
        if bonus_card and customer_profile:
            visit_history = self._create_customer_visit_history(
                customer, station, tid, sale_date, sale_time,
                product, amount, quantity, approval_number, bonus_card
            )
            
        return {
            'excel_data': excel_data,
            'sales_statistics': sales_stat,
            'visit_history': visit_history,
            'customer': customer,
            'station': station,
            'tid': tid
        }
    
    def _create_excel_sales_data(self, tid, sale_date, sale_time, customer, 
                               product, quantity, unit_price, total_amount, 
                               approval_number, bonus_card):
        """ExcelSalesData 생성"""
        
        payment_type = random.choice(self.payment_types)
        sale_type = random.choice(self.sale_types)
        
        excel_data = ExcelSalesData.objects.create(
            tid=tid,
            sale_date=sale_date,
            sale_time=sale_time,
            customer_number=f"C{customer.id:06d}",
            customer_name=customer.username,
            issue_number=f"ISS{random.randint(100000, 999999)}",
            product_type='석유제품',
            sale_type=sale_type,
            payment_type=payment_type,
            sale_type2='일반판매',
            nozzle=str(random.randint(1, 8)),
            product_code=f"P{random.randint(100, 999)}",
            product_pack=product,
            quantity=Decimal(str(quantity)),
            unit_price=Decimal(str(unit_price)),
            total_amount=Decimal(str(total_amount)),
            earned_points=int(total_amount * 0.01),  # 1% 적립
            points=0,
            bonus=0,
            pos_id=f"POS{random.randint(1, 5)}",
            pos_code='P001',
            store=tid,
            receipt=f"R{datetime.now().strftime('%Y%m%d%H%M%S')}",
            approval_number=approval_number,
            approval_datetime=datetime.now(),
            bonus_card=bonus_card,
            customer_card_number=bonus_card,
            data_created_at=datetime.now(),
            source_file='test_script.xlsx'
        )
        
        print(f"✅ ExcelSalesData 생성 완료 (ID: {excel_data.id})")
        return excel_data
    
    def _update_sales_statistics(self, tid, sale_date):
        """SalesStatistics 업데이트"""
        
        # 해당 날짜의 모든 ExcelSalesData 집계
        daily_data = ExcelSalesData.objects.filter(
            tid=tid,
            sale_date=sale_date
        )
        
        if not daily_data.exists():
            print("⚠️  통계 데이터가 없습니다.")
            return None
            
        # 집계
        stats = daily_data.aggregate(
            total_amount=Sum('total_amount'),
            total_quantity=Sum('quantity'),
            total_count=Count('id')
        )
        
        # 제품별 집계
        product_stats = {}
        for data in daily_data:
            product = data.product_pack
            if product:
                product_stats[product] = product_stats.get(product, 0) + 1
                
        top_product = max(product_stats.items(), key=lambda x: x[1])[0] if product_stats else ''
        top_count = max(product_stats.values()) if product_stats else 0
        
        # 기존 통계 확인
        existing = SalesStatistics.objects.filter(
            tid=tid,
            sale_date=sale_date
        ).first()
        
        if existing:
            # 업데이트
            existing.total_transactions = stats['total_count']
            existing.total_amount = stats['total_amount'] or 0
            existing.total_quantity = stats['total_quantity'] or 0
            existing.avg_unit_price = stats['total_amount'] / stats['total_count'] if stats['total_count'] > 0 else 0
            existing.top_product = top_product
            existing.top_product_count = top_count
            existing.save()
            print(f"✅ SalesStatistics 업데이트 완료")
            return existing
        else:
            # 생성
            sales_stat = SalesStatistics.objects.create(
                tid=tid,
                sale_date=sale_date,
                total_transactions=stats['total_count'],
                total_amount=stats['total_amount'] or 0,
                total_quantity=stats['total_quantity'] or 0,
                avg_unit_price=stats['total_amount'] / stats['total_count'] if stats['total_count'] > 0 else 0,
                top_product=top_product,
                top_product_count=top_count,
                source_file='test_script'
            )
            print(f"✅ SalesStatistics 생성 완료")
            return sales_stat
    
    def _create_customer_visit_history(self, customer, station, tid, sale_date, 
                                     sale_time, product, amount, quantity, 
                                     approval_number, bonus_card):
        """CustomerVisitHistory 생성"""
        
        # 중복 확인
        existing = CustomerVisitHistory.objects.filter(
            customer=customer,
            station=station,
            visit_date=sale_date,
            visit_time=sale_time,
            approval_number=approval_number
        ).first()
        
        if existing:
            existing.delete()
            print("⚠️  기존 방문 기록 삭제")
            
        visit = CustomerVisitHistory.objects.create(
            customer=customer,
            station=station,
            tid=tid,
            visit_date=sale_date,
            visit_time=sale_time,
            payment_type=random.choice(self.payment_types),
            product_pack=product,
            sale_amount=Decimal(str(amount)),
            fuel_quantity=Decimal(str(quantity)),
            approval_number=approval_number,
            membership_card=bonus_card
        )
        
        print(f"✅ CustomerVisitHistory 생성 완료")
        return visit
    
    def generate_multiple_sales(self, customer_username, station_username, 
                              amounts, days_back=7):
        """
        여러 건의 매출 데이터 생성
        
        Parameters:
        -----------
        customer_username : str
            고객 사용자명
        station_username : str
            주유소 사용자명
        amounts : list
            금액 리스트
        days_back : int
            며칠 전부터 생성할지 (기본값: 7일)
        """
        
        results = []
        for i, amount in enumerate(amounts):
            sale_date = datetime.now().date() - timedelta(days=days_back-i)
            result = self.generate_sales_data(
                customer_username, 
                station_username, 
                amount,
                sale_date=sale_date
            )
            if result:
                results.append(result)
                
        return results


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 엑셀 매출 데이터 테스트 생성기")
    print("=" * 60)
    
    generator = ExcelSalesDataGenerator()
    
    while True:
        print("\n📋 메뉴:")
        print("1. 단일 매출 데이터 생성")
        print("2. 여러 건 매출 데이터 생성")
        print("3. 빠른 테스트 (richard2 @ richard)")
        print("4. 통계 확인")
        print("0. 종료")
        print("-" * 40)
        
        choice = input("선택: ")
        
        if choice == '1':
            # 단일 매출
            customer = input("고객 username (기본: richard2): ") or "richard2"
            station = input("주유소 username (기본: richard): ") or "richard"
            amount = float(input("금액 (기본: 50000): ") or "50000")
            
            generator.generate_sales_data(customer, station, amount)
            
        elif choice == '2':
            # 여러 건
            customer = input("고객 username (기본: richard2): ") or "richard2"
            station = input("주유소 username (기본: richard): ") or "richard"
            count = int(input("생성할 개수 (기본: 5): ") or "5")
            
            amounts = []
            for i in range(count):
                amount = random.randint(30000, 100000)
                amounts.append(amount)
                
            generator.generate_multiple_sales(customer, station, amounts)
            
        elif choice == '3':
            # 빠른 테스트
            print("\n🚀 빠른 테스트 실행")
            amounts = [50000, 30000, 40000, 20000, 35000]
            generator.generate_multiple_sales("richard2", "richard", amounts, days_back=5)
            
        elif choice == '4':
            # 통계 확인
            station_username = input("주유소 username (기본: richard): ") or "richard"
            
            try:
                station = User.objects.get(username=station_username, user_type='STATION')
                station_profile = StationProfile.objects.filter(user=station).first()
                tid = station_profile.tid if station_profile else f"TID_{station.id}"
                
                # 최근 7일 통계
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=6)
                
                stats = SalesStatistics.objects.filter(
                    tid=tid,
                    sale_date__range=[start_date, end_date]
                ).order_by('-sale_date')
                
                print(f"\n📊 {station_username} 주유소 최근 7일 통계:")
                print("-" * 60)
                for stat in stats:
                    print(f"{stat.sale_date}: {stat.total_transactions}건, {stat.total_amount:,.0f}원")
                    
            except User.DoesNotExist:
                print("❌ 주유소를 찾을 수 없습니다.")
                
        elif choice == '0':
            print("\n👋 종료합니다.")
            break
            
        input("\nEnter를 눌러 계속...")


if __name__ == '__main__':
    main()