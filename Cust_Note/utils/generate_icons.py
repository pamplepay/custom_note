#!/usr/bin/env python3
"""
PWA 아이콘 생성 스크립트
SVG 파일을 다양한 크기의 PNG 파일로 변환합니다.
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon_png(size, filename):
    """단순한 PNG 아이콘을 생성합니다."""
    # 새 이미지 생성 (RGBA 모드로 투명도 지원)
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 배경 원형 (파란색 그라데이션 효과)
    margin = size // 20
    draw.ellipse([margin, margin, size-margin, size-margin], 
                fill=(0, 123, 255, 255), outline=(0, 86, 179, 255), width=max(1, size//64))
    
    # 주유기 본체
    pump_width = size // 3
    pump_height = size // 2
    pump_x = (size - pump_width) // 2
    pump_y = size // 3
    
    draw.rectangle([pump_x, pump_y, pump_x + pump_width, pump_y + pump_height],
                  fill=(255, 255, 255, 255), outline=(0, 123, 255, 255), width=max(1, size//128))
    
    # 디스플레이 화면
    display_margin = pump_width // 8
    display_height = pump_height // 4
    draw.rectangle([pump_x + display_margin, pump_y + display_margin,
                   pump_x + pump_width - display_margin, pump_y + display_margin + display_height],
                  fill=(26, 26, 26, 255), outline=(51, 51, 51, 255), width=max(1, size//256))
    
    # 주유건 호스 (간단한 곡선)
    hose_start_x = pump_x + pump_width
    hose_start_y = pump_y + pump_height // 2
    hose_end_x = size - margin - size//10
    hose_end_y = pump_y + pump_height - pump_height//4
    
    # 호스 그리기 (여러 개의 선분으로 곡선 효과)
    for i in range(5):
        x1 = hose_start_x + (hose_end_x - hose_start_x) * i // 5
        y1 = hose_start_y + (hose_end_y - hose_start_y) * i // 5
        x2 = hose_start_x + (hose_end_x - hose_start_x) * (i + 1) // 5
        y2 = hose_start_y + (hose_end_y - hose_start_y) * (i + 1) // 5
        draw.line([x1, y1, x2, y2], fill=(51, 51, 51, 255), width=max(2, size//64))
    
    # 주유건
    nozzle_size = size // 20
    draw.ellipse([hose_end_x - nozzle_size//2, hose_end_y - nozzle_size,
                 hose_end_x + nozzle_size//2, hose_end_y + nozzle_size],
                fill=(51, 51, 51, 255))
    
    # 버튼들 (3개의 작은 원)
    button_y = pump_y + pump_height // 2
    button_radius = max(2, size // 40)
    colors = [(40, 167, 69), (255, 193, 7), (220, 53, 69)]  # 초록, 노랑, 빨강
    
    for i, color in enumerate(colors):
        button_x = pump_x + pump_width // 4 + i * pump_width // 4
        draw.ellipse([button_x - button_radius, button_y - button_radius,
                     button_x + button_radius, button_y + button_radius],
                    fill=color)
    
    # 로고 "O" 텍스트 (상단)
    try:
        # 폰트 크기 계산
        font_size = max(12, size // 8)
        # 기본 폰트 사용
        font = ImageFont.load_default()
        
        logo_y = pump_y - size // 8
        text = "O"
        
        # 텍스트 크기 계산
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 텍스트 배경 원
        logo_radius = max(text_width, text_height) + size // 20
        draw.ellipse([size//2 - logo_radius, logo_y - logo_radius,
                     size//2 + logo_radius, logo_y + logo_radius],
                    fill=(255, 255, 255, 255), outline=(0, 123, 255, 255), width=max(1, size//128))
        
        # 텍스트 그리기
        draw.text((size//2 - text_width//2, logo_y - text_height//2), text, 
                 fill=(0, 123, 255, 255), font=font)
    except:
        # 폰트 로드 실패 시 단순한 원만 그리기
        logo_radius = size // 15
        draw.ellipse([size//2 - logo_radius, pump_y - size//8 - logo_radius,
                     size//2 + logo_radius, pump_y - size//8 + logo_radius],
                    fill=(255, 255, 255, 255), outline=(0, 123, 255, 255), width=max(1, size//128))
    
    # 파일 저장
    img.save(filename, 'PNG', quality=95)
    print(f"아이콘 생성 완료: {filename} ({size}x{size})")

def main():
    """메인 함수"""
    # 아이콘 크기와 파일명 정의
    icons = [
        (192, 'icon-192x192.png'),
        (512, 'icon-512x512.png')
    ]
    
    # PWA 아이콘 디렉토리 (utils에서 static/pwa/icons로)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # Cust_Note 디렉토리
    pwa_icons_dir = os.path.join(project_root, 'static', 'pwa', 'icons')
    
    # 디렉토리가 없으면 생성
    os.makedirs(pwa_icons_dir, exist_ok=True)
    
    # 각 크기별 아이콘 생성
    for size, filename in icons:
        filepath = os.path.join(pwa_icons_dir, filename)
        create_icon_png(size, filepath)
    
    print("모든 PWA 아이콘 생성이 완료되었습니다!")
    print(f"아이콘 저장 위치: {pwa_icons_dir}")

if __name__ == "__main__":
    main() 