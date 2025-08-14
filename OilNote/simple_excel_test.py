#!/usr/bin/env python
"""
간단한 엑셀 매출 데이터 테스트
보너스카드 없이 기본 데이터만 생성
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from test_excel_sales_data import ExcelSalesDataGenerator

def quick_test():
    """빠른 테스트 실행"""
    generator = ExcelSalesDataGenerator()
    
    # 단일 매출 생성 (보너스카드 없이)
    print("\n=== 단일 매출 데이터 생성 (보너스카드 없음) ===")
    result = generator.generate_sales_data(
        customer_username="richard2",
        station_username="richard",
        amount=10000,
        skip_bonus_card=True  # 보너스카드 없이
    )
    
    if result:
        print("\n✅ 생성 완료:")
        print(f"   ExcelSalesData ID: {result['excel_data'].id}")
        print(f"   SalesStatistics: {result['sales_statistics']}")
        print(f"   CustomerVisitHistory: {result['visit_history']}") # None이어야 함

if __name__ == '__main__':
    quick_test()