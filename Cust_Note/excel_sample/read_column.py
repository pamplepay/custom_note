import pandas as pd

# 엑셀 파일 경로
excel_file = '../1234567890_20250701.xlsx'

# 엑셀 파일 읽기 (헤더 없음, 4행부터 시작)
df = pd.read_excel(excel_file, header=None, skiprows=3)

# 5번째 열(인덱스 4) 데이터 출력
print("\n=== 5번째 열(고객명) 데이터 ===")
print(df[4].unique())  # 중복 제거된 고유값들 출력
print("\n=== 데이터 샘플(처음 5개) ===")
print(df[4].head()) 