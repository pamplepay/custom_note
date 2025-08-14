#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_StationApp.models import PhoneCardMapping, PointCard
from OilNote_User.models import CustomUser

def check_station_data():
    print('=== 주유소 고객 등록 데이터 확인 ===')
    
    # 1. 전화번호 01033331111 관련 데이터 확인
    print('\n--- 전화번호 01033331111 관련 데이터 ---')
    phone_mappings = PhoneCardMapping.objects.filter(phone_number='01033331111')
    print(f'전화번호 01033331111 매핑 수: {phone_mappings.count()}')
    
    for mapping in phone_mappings:
        linked_user = mapping.linked_user.username if mapping.linked_user else "없음"
        station_name = mapping.station.station_profile.station_name if hasattr(mapping.station, 'station_profile') else mapping.station.username
        print(f'매핑 ID: {mapping.id}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {linked_user}, 등록주유소: {station_name}')
    
    # 2. 카드번호 8851111122223001 관련 데이터 확인
    print('\n--- 카드번호 8851111122223001 관련 데이터 ---')
    try:
        card = PointCard.objects.get(number='8851111122223001')
        print(f'카드 정보: {card.full_number}, 사용여부: {card.is_used}')
        
        # 이 카드와 연동된 PhoneCardMapping 확인
        card_mappings = PhoneCardMapping.objects.filter(membership_card=card)
        print(f'이 카드와 연동된 매핑 수: {card_mappings.count()}')
        
        for mapping in card_mappings:
            linked_user = mapping.linked_user.username if mapping.linked_user else "없음"
            print(f'매핑 ID: {mapping.id}, 전화번호: {mapping.phone_number}, 사용여부: {mapping.is_used}, 연동사용자: {linked_user}')
    except PointCard.DoesNotExist:
        print('카드번호 8851111122223001을 찾을 수 없습니다.')
    
    # 3. 최근 생성된 PhoneCardMapping 확인
    print('\n--- 최근 생성된 PhoneCardMapping ---')
    recent_mappings = PhoneCardMapping.objects.order_by('-created_at')[:5]
    for mapping in recent_mappings:
        linked_user = mapping.linked_user.username if mapping.linked_user else "없음"
        station_name = mapping.station.station_profile.station_name if hasattr(mapping.station, 'station_profile') else mapping.station.username
        print(f'생성시간: {mapping.created_at}, 전화번호: {mapping.phone_number}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {linked_user}, 주유소: {station_name}')
    
    # 4. 미사용 카드 확인
    print('\n--- 미사용 카드 목록 ---')
    unused_mappings = PhoneCardMapping.objects.filter(is_used=False)
    print(f'미사용 매핑 수: {unused_mappings.count()}')
    
    for mapping in unused_mappings:
        station_name = mapping.station.station_profile.station_name if hasattr(mapping.station, 'station_profile') else mapping.station.username
        print(f'전화번호: {mapping.phone_number}, 카드: {mapping.membership_card.full_number}, 주유소: {station_name}')

if __name__ == '__main__':
    check_station_data() 