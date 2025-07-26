#!/usr/bin/env python
"""
간단한 엑셀 매출 데이터 테스트
보너스카드 없이 기본 데이터만 생성
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from test_excel_sales_data import ExcelSalesDataGenerator

def quick_test():
    """빠른 테스트 실행"""
    generator = ExcelSalesDataGenerator()
    
    # 전월 날짜 계산
    today = datetime.now()
    if today.month == 1:
        previous_month_date = datetime(today.year - 1, 12, 15)  # 작년 12월 15일
    else:
        previous_month_date = datetime(today.year, today.month - 1, 15)  # 전월 15일
    
    sale_date = previous_month_date.strftime('%Y-%m-%d')
    
    # 단일 매출 생성 (보너스카드 없이)
    print("\n=== 단일 매출 데이터 생성 (보너스카드 없음) ===")
    print(f"매출 날짜: {sale_date} (전월)")
    
    result = generator.generate_sales_data(
        customer_username="richard2",
        station_username="richard",
        amount=10000,
        sale_date=sale_date,  # 전월 날짜 추가
        skip_bonus_card=True  # 보너스카드 없이
    )
    
    if result:
        print("\n✅ 생성 완료:")
        print(f"   ExcelSalesData ID: {result['excel_data'].id}")
        print(f"   SalesStatistics: {result['sales_statistics']}")
        print(f"   CustomerVisitHistory: {result['visit_history']}") # None이어야 함

if __name__ == '__main__':
    quick_test()