import os
import sys
import django
import pandas as pd
from datetime import datetime

# Django 설정 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from excel_sample.models import SalesData

# 엑셀 파일 읽기 (헤더 없음, 4행부터 시작)
excel_file = '../1234567890_20250701.xlsx'
df = pd.read_excel(excel_file, header=None, skiprows=3)

# 6번째 행 가져오기 (인덱스 2, 4행부터 시작했으므로)
row = df.iloc[2]

try:
    # 날짜와 시간 처리
    sale_datetime = datetime.strptime(str(row[2]), '%Y/%m/%d %H:%M')
    sale_date = datetime.strptime(str(row[1]), '%Y/%m/%d').date()
    
    # 데이터 모델에 저장
    sales_data = SalesData(
        blank_column=str(row[0]) if pd.notna(row[0]) else None,
        sale_date=sale_date,
        sale_time=sale_datetime.time(),
        customer_number=str(row[3]) if pd.notna(row[3]) else None,
        customer_name=str(row[4]) if pd.notna(row[4]) else None,
        issue_number=str(row[5]) if pd.notna(row[5]) else None,
        product_type=str(row[6]) if pd.notna(row[6]) else None,
        sale_type=str(row[7]) if pd.notna(row[7]) else None,
        payment_type=str(row[8]) if pd.notna(row[8]) else None,
        sale_type2=str(row[9]) if pd.notna(row[9]) else None,
        nozzle=str(row[10]) if pd.notna(row[10]) else None,
        product_code=str(row[11]) if pd.notna(row[11]) else None,
        product_pack=str(row[12]) if pd.notna(row[12]) else None,
        quantity=float(row[13]) if pd.notna(row[13]) else 0,
        unit_price=float(row[14]) if pd.notna(row[14]) else 0,
        total_amount=float(row[15]) if pd.notna(row[15]) else 0,
        earned_points=0,  # 문자열 데이터라서 0으로 설정
        points=0,  # 문자열 데이터라서 0으로 설정
        bonus=0,  # 문자열 데이터라서 0으로 설정
        pos_id=str(row[19]) if pd.notna(row[19]) else None,
        pos_code=str(row[20]) if pd.notna(row[20]) else None,
        store=str(row[21]) if pd.notna(row[21]) else None,
        receipt=str(row[22]) if pd.notna(row[22]) else None,
        approval_number=str(row[23]) if pd.notna(row[23]) else None,
        approval_datetime=datetime.strptime(str(row[24]), '%Y/%m/%d %H:%M') if pd.notna(row[24]) else None,
        bonus_card=str(row[25]) if pd.notna(row[25]) else None,
        customer_card_number=str(row[26]) if pd.notna(row[26]) else None,
        data_created_at=datetime.strptime(str(row[27]), '%Y/%m/%d %H:%M') if pd.notna(row[27]) else None
    )
    sales_data.save()
    print("6번째 행 데이터가 성공적으로 저장되었습니다.")
    
    # 저장된 데이터 출력
    print("\n=== 저장된 데이터 ===")
    print(f"판매일자: {sales_data.sale_date}")
    print(f"주유시간: {sales_data.sale_time}")
    print(f"고객명: {sales_data.customer_name}")
    print(f"제품/PACK: {sales_data.product_pack}")
    print(f"판매수량: {sales_data.quantity}")
    print(f"판매금액: {sales_data.total_amount}")
    print(f"승인번호: {sales_data.approval_number}")

except Exception as e:
    print(f"오류 발생: {e}")
    
# 원본 데이터 출력
print("\n=== 원본 엑셀 데이터 ===")
print(row.to_dict()) 