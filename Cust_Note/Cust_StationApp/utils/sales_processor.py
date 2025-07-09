import pandas as pd
import numpy as np
from datetime import datetime
import os
import logging
from typing import Dict, Tuple, Optional, List

logger = logging.getLogger(__name__)

class SalesDataProcessor:
    """매출 데이터 처리를 위한 클래스"""
    
    def __init__(self):
        self.required_columns = {
            'date': ['날짜', '일자', '거래일자', '매출일자'],
            'amount': ['금액', '매출액', '매출금액', '거래금액', '합계']
        }
        
    def process_excel_file(self, file_path: str) -> Tuple[bool, Dict, str]:
        """
        엑셀 파일을 처리하여 매출 데이터를 추출
        
        Args:
            file_path (str): 엑셀 파일 경로
            
        Returns:
            Tuple[bool, Dict, str]: (성공 여부, 처리된 데이터, 오류 메시지)
        """
        try:
            # 엑셀 파일의 모든 시트 읽기
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            if not sheet_names:
                return False, {}, "엑셀 파일에 시트가 없습니다."
            
            # 2번째 행을 헤더로 사용하여 데이터 읽기 (3번째 행부터 실제 데이터)
            df = pd.read_excel(file_path, sheet_name=sheet_names[0], header=2)
            
            # 데이터 전처리
            df = self._preprocess_dataframe(df)
            
            # 실제 컬럼 구조 로깅
            actual_columns = df.columns.tolist()
            logger.info(f"실제 데이터 컬럼: {actual_columns}")
            
            # 필수 컬럼 찾기
            date_col = self._find_column(df, self.required_columns['date'])
            amount_col = self._find_column(df, self.required_columns['amount'])
            
            if not date_col or not amount_col:
                return False, {}, f"날짜 또는 금액 컬럼을 찾을 수 없습니다. 현재 컬럼: {actual_columns}"
            
            # 데이터 정리
            first_date = df[date_col].iloc[0]
            sales_date = first_date.strftime('%Y-%m-%d') if isinstance(first_date, pd.Timestamp) else str(first_date) if pd.notna(first_date) else None
            
            processed_data = {
                'sales_date': sales_date,
                'total_sales': float(df[amount_col].sum()),
                'details': self._extract_details(df, date_col, amount_col),
                'columns': actual_columns  # 실제 컬럼 정보 포함
            }
            
            return True, processed_data, ""
            
        except Exception as e:
            logger.error(f"엑셀 파일 처리 중 오류 발생: {str(e)}", exc_info=True)
            return False, {}, f"파일 처리 중 오류가 발생했습니다: {str(e)}"
    
    def _preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터프레임 전처리"""
        # Unnamed 컬럼 제거
        unnamed_cols = [col for col in df.columns if 'Unnamed' in str(col)]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)
        
        # 컬럼명 정리
        df.columns = [str(col).strip() for col in df.columns]
        
        # 결측치 처리
        df = df.replace({np.nan: None})
        
        # 숫자로 된 날짜를 datetime으로 변환
        for col in df.columns:
            if df[col].dtype == 'int64' and any(keyword in col.lower() for keyword in self.required_columns['date']):
                try:
                    df[col] = pd.to_datetime(df[col], format='%Y%m%d')
                except:
                    pass
        
        return df
    
    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """주어진 이름 목록에서 실제 컬럼명 찾기"""
        for col in df.columns:
            for name in possible_names:
                if name in col:
                    return col
        return None
    
    def _extract_details(self, df: pd.DataFrame, date_col: str, amount_col: str) -> List[Dict]:
        """상세 매출 데이터 추출"""
        details = []
        for idx in range(len(df)):
            row = df.iloc[idx]
            date_value = row[date_col]
            amount_value = row[amount_col]
            
            if pd.notna(date_value) and pd.notna(amount_value):
                detail = {
                    'date': date_value.strftime('%Y-%m-%d') if isinstance(date_value, pd.Timestamp) else str(date_value),
                    'amount': float(amount_value)
                }
                details.append(detail)
        return details
    
    def validate_file_format(self, file_path: str) -> Tuple[bool, str]:
        """파일 형식 검증"""
        try:
            # 파일 확장자 검사
            if not file_path.endswith('.xlsx'):
                return False, "엑셀 파일(.xlsx)만 업로드 가능합니다."
            
            # 파일 존재 여부 검사
            if not os.path.exists(file_path):
                return False, "파일이 존재하지 않습니다."
            
            # 파일 크기 검사 (10MB 제한)
            if os.path.getsize(file_path) > 10 * 1024 * 1024:
                return False, "파일 크기가 10MB를 초과합니다."
            
            return True, ""
            
        except Exception as e:
            logger.error(f"파일 검증 중 오류 발생: {str(e)}", exc_info=True)
            return False, f"파일 검증 중 오류가 발생했습니다: {str(e)}"
    
    def get_file_info(self, file_path: str) -> Dict:
        """파일 정보 추출"""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        created_time = datetime.fromtimestamp(os.path.getctime(file_path))
        
        return {
            'file_name': file_name,
            'file_size': file_size,
            'created_at': created_time
        } 