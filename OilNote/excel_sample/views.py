from django.shortcuts import render
import pandas as pd
from datetime import datetime
from django.utils import timezone
from .models import SalesData
import logging
import sys
import os

# Create your views here.

def process_sample_excel():
    # 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)

    try:
        # 파일 경로 (절대 경로 사용)
        file_path = '/home/oilnote/custom_note/OilNote/1234567890_20250701.xlsx'
        logger.debug(f"엑셀 파일 읽기 시작: {file_path}")

        # 엑셀 파일 읽기 - 헤더 행을 직접 지정
        df = pd.read_excel(
            file_path,
            skiprows=4,  # 처음 4행은 건너뛰기
            names=['판매일자', '주유시간', '고객번호', '고객명', '발행번호', '주류상품종류', 
                  '판매구분', '결제구분', '판매구분2', '노즐', '제품코드', '제품/PACK',
                  '판매수량', '판매단가', '판매금액', '적립포인트', '포인트', '보너스',
                  'POS_ID', 'POS코드', '판매점', '영수증', '승인번호', '승인일시',
                  '보너스카드', '고객카드번호', '데이터생성일시']
        )
        logger.debug(f"엑셀 파일 읽기 완료. 총 {len(df)} 행 발견")
        
        # 첫 번째 행 데이터 가져오기
        first_row = df.iloc[0]
        logger.debug("첫 번째 행 데이터:")
        for column in df.columns:
            logger.debug(f"{column}: {first_row[column]}")

        # 날짜/시간 문자열 파싱
        try:
            sale_date_str = str(first_row['판매일자'])
            sale_time_str = str(first_row['주유시간'])
            logger.debug(f"날짜 문자열: {sale_date_str}, 시간 문자열: {sale_time_str}")

            # 날짜 파싱 (YYYY/MM/DD 형식)
            sale_date = datetime.strptime(sale_date_str, '%Y/%m/%d').date()
            # 시간 파싱 (YYYY/MM/DD HH:MM 형식에서 시간만 추출)
            sale_time = datetime.strptime(sale_time_str.split(' ')[1], '%H:%M').time()
            
            logger.debug(f"파싱된 날짜: {sale_date}, 파싱된 시간: {sale_time}")
        except ValueError as e:
            logger.error(f"날짜/시간 파싱 오류: {e}")
            return

        # 승인일시 처리
        try:
            approval_datetime = timezone.now()  # timezone-aware datetime 사용
            logger.debug(f"승인일시 설정: {approval_datetime}")
        except ValueError as e:
            logger.error(f"승인일시 처리 오류: {e}")
            return

        # 숫자 데이터 처리
        try:
            quantity = float(first_row['판매수량'])
            unit_price = float(first_row['판매단가'])
            total_amount = float(first_row['판매금액'])
            logger.debug(f"수량: {quantity}, 단가: {unit_price}, 금액: {total_amount}")
        except (ValueError, KeyError) as e:
            logger.error(f"숫자 데이터 처리 오류: {e}")
            return

        # 데이터베이스 레코드 생성
        try:
            sales_data = SalesData(
                sale_date=sale_date,
                sale_time=sale_time,
                payment_type=str(first_row.get('결제구분', '')),
                product_code=str(first_row.get('제품코드', '')),
                product_pack=str(first_row.get('제품/PACK', '')),
                quantity=quantity,
                unit_price=unit_price,
                total_amount=total_amount,
                approval_number=str(first_row.get('승인번호', '')),
                approval_datetime=approval_datetime,
                bonus_card=str(first_row.get('보너스카드', '')),
                customer_card_number=str(first_row.get('고객카드번호', '')),
                data_created_at=timezone.now()
            )
            
            logger.debug("데이터베이스 레코드 생성 준비 완료")
            logger.debug(f"생성될 레코드 정보: {sales_data.__dict__}")
            
            sales_data.save()
            logger.info("데이터베이스 저장 완료!")
            
        except Exception as e:
            logger.error(f"데이터베이스 저장 중 오류 발생: {e}")
            return

    except FileNotFoundError:
        logger.error(f"파일을 찾을 수 없음: {file_path}")
    except Exception as e:
        logger.error(f"처리 중 예상치 못한 오류 발생: {e}")

if __name__ == "__main__":
    process_sample_excel()
