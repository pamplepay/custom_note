from django.core.management.base import BaseCommand
import pandas as pd
import logging
import sys
import os
from datetime import datetime

class Command(BaseCommand):
    help = '엑셀 파일의 데이터 행 개수를 파악합니다.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='분석할 엑셀 파일 경로')

    def handle(self, *args, **options):
        # 로깅 설정
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            stream=sys.stdout
        )
        logger = logging.getLogger(__name__)

        file_path = options['file_path']
        
        try:
            logger.info(f"=== 엑셀 파일 데이터 행 개수 분석 시작 ===")
            logger.info(f"파일 경로: {file_path}")
            
            # 파일 존재 확인
            if not os.path.exists(file_path):
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return
            
            # 파일 크기 확인
            file_size = os.path.getsize(file_path)
            logger.info(f"파일 크기: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
            
            # 파일 수정 시간 확인
            file_mtime = os.path.getmtime(file_path)
            file_mtime_str = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"파일 수정 시간: {file_mtime_str}")
            
            # 엑셀 파일 읽기
            logger.info("엑셀 파일 읽기 시작...")
            
            # 먼저 헤더 정보 확인
            df_header = pd.read_excel(file_path, nrows=10)
            logger.info(f"파일의 처음 10행 미리보기:")
            logger.info(f"컬럼 개수: {len(df_header.columns)}")
            logger.info(f"컬럼명: {list(df_header.columns)}")
            
            # 전체 데이터 읽기 (첫 번째 행부터 시작)
            df = pd.read_excel(
                file_path,
                skiprows=0,  # 첫 번째 행부터 시작
                names=['판매일자', '주유시간', '고객번호', '고객명', '발행번호', '주류상품종류', 
                      '판매구분', '결제구분', '판매구분2', '노즐', '제품코드', '제품/PACK',
                      '판매수량', '판매단가', '판매금액', '적립포인트', '포인트', '보너스',
                      'POS_ID', 'POS코드', '판매점', '영수증', '승인번호', '승인일시',
                      '보너스카드', '고객카드번호', '데이터생성일시']
            )
            
            # 데이터 분석 결과
            total_rows = len(df)
            logger.info(f"=== 분석 결과 ===")
            logger.info(f"총 데이터 행 개수: {total_rows:,} 행")
            
            # 빈 행 제거 후 실제 데이터 행 개수
            df_cleaned = df.dropna(how='all')
            actual_data_rows = len(df_cleaned)
            logger.info(f"실제 데이터 행 개수 (빈 행 제외): {actual_data_rows:,} 행")
            logger.info(f"빈 행 개수: {total_rows - actual_data_rows:,} 행")
            
            # 첫 번째와 마지막 데이터 행 정보
            if actual_data_rows > 0:
                first_row = df_cleaned.iloc[0]
                last_row = df_cleaned.iloc[-1]
                
                logger.info(f"=== 첫 번째 데이터 행 ===")
                logger.info(f"판매일자: {first_row['판매일자']}")
                logger.info(f"주유시간: {first_row['주유시간']}")
                logger.info(f"고객명: {first_row['고객명']}")
                logger.info(f"제품/PACK: {first_row['제품/PACK']}")
                logger.info(f"판매수량: {first_row['판매수량']}")
                logger.info(f"판매금액: {first_row['판매금액']}")
                
                logger.info(f"=== 마지막 데이터 행 ===")
                logger.info(f"판매일자: {last_row['판매일자']}")
                logger.info(f"주유시간: {last_row['주유시간']}")
                logger.info(f"고객명: {last_row['고객명']}")
                logger.info(f"제품/PACK: {last_row['제품/PACK']}")
                logger.info(f"판매수량: {last_row['판매수량']}")
                logger.info(f"판매금액: {last_row['판매금액']}")
            
            # 날짜 범위 확인
            if actual_data_rows > 0:
                try:
                    # 판매일자 컬럼에서 날짜 정보 추출
                    sale_dates = df_cleaned['판매일자'].dropna()
                    if len(sale_dates) > 0:
                        min_date = sale_dates.min()
                        max_date = sale_dates.max()
                        logger.info(f"=== 날짜 범위 ===")
                        logger.info(f"최초 판매일: {min_date}")
                        logger.info(f"최종 판매일: {max_date}")
                        
                        # 날짜별 데이터 개수
                        date_counts = sale_dates.value_counts().sort_index()
                        logger.info(f"날짜별 데이터 개수:")
                        for date, count in date_counts.head(10).items():
                            logger.info(f"  {date}: {count:,} 행")
                        if len(date_counts) > 10:
                            logger.info(f"  ... (총 {len(date_counts)}개 날짜)")
                except Exception as e:
                    logger.warning(f"날짜 범위 분석 중 오류: {e}")
            
            # 제품별 데이터 개수
            if actual_data_rows > 0:
                try:
                    product_counts = df_cleaned['제품/PACK'].value_counts()
                    logger.info(f"=== 제품별 데이터 개수 (상위 10개) ===")
                    for product, count in product_counts.head(10).items():
                        logger.info(f"  {product}: {count:,} 행")
                    if len(product_counts) > 10:
                        logger.info(f"  ... (총 {len(product_counts)}개 제품)")
                except Exception as e:
                    logger.warning(f"제품별 분석 중 오류: {e}")
            
            # 메모리 사용량 확인
            memory_usage = df.memory_usage(deep=True).sum()
            logger.info(f"=== 메모리 사용량 ===")
            logger.info(f"데이터프레임 메모리 사용량: {memory_usage:,} bytes ({memory_usage/1024/1024:.2f} MB)")
            
            logger.info(f"=== 분석 완료 ===")
            
        except FileNotFoundError:
            logger.error(f"파일을 찾을 수 없습니다: {file_path}")
        except Exception as e:
            logger.error(f"분석 중 오류 발생: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}") 