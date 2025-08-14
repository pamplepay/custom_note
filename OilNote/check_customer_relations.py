#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_User.models import CustomUser, CustomerStationRelation
from OilNote_StationApp.models import PhoneCardMapping

def check_customer_relations():
    print('=== 고객 관계 데이터 확인 ===')
    
    # 1. 모든 고객 사용자 확인
    print('\n--- 모든 고객 사용자 ---')
    customers = CustomUser.objects.filter(user_type='CUSTOMER')
    print(f'총 고객 사용자 수: {customers.count()}')
    
    for customer in customers:
        try:
            profile = customer.customer_profile
            phone = getattr(profile, 'customer_phone', '없음')
            print(f'ID: {customer.id}, 사용자명: {customer.username}, 전화번호: {phone}')
        except Exception as e:
            print(f'ID: {customer.id}, 사용자명: {customer.username}, 프로필 오류: {e}')
    
    # 2. 주유소별 고객 관계 확인
    print('\n--- 주유소별 고객 관계 ---')
    stations = CustomUser.objects.filter(user_type='STATION')
    
    for station in stations:
        station_name = station.station_profile.station_name if hasattr(station, 'station_profile') else station.username
        relations = CustomerStationRelation.objects.filter(station=station)
        print(f'\n주유소: {station_name} (ID: {station.id})')
        print(f'등록된 고객 수: {relations.count()}')
        
        for relation in relations:
            try:
                customer = relation.customer
                profile = customer.customer_profile
                phone = getattr(profile, 'customer_phone', '없음')
                print(f'  - 고객: {customer.username} (전화번호: {phone})')
            except Exception as e:
                print(f'  - 고객: {relation.customer.username} (오류: {e})')
    
    # 3. PhoneCardMapping 상태 확인
    print('\n--- PhoneCardMapping 상태 ---')
    phone_mappings = PhoneCardMapping.objects.all()
    print(f'총 PhoneCardMapping 수: {phone_mappings.count()}')
    
    for mapping in phone_mappings:
        station_name = mapping.station.station_profile.station_name if hasattr(mapping.station, 'station_profile') else mapping.station.username
        linked_user = mapping.linked_user.username if mapping.linked_user else "없음"
        print(f'전화번호: {mapping.phone_number}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {linked_user}, 주유소: {station_name}')
    
    # 4. 미사용 PhoneCardMapping 확인
    print('\n--- 미사용 PhoneCardMapping (고객 등록 대기) ---')
    unused_mappings = PhoneCardMapping.objects.filter(is_used=False)
    print(f'미사용 매핑 수: {unused_mappings.count()}')
    
    for mapping in unused_mappings:
        station_name = mapping.station.station_profile.station_name if hasattr(mapping.station, 'station_profile') else mapping.station.username
        print(f'전화번호: {mapping.phone_number}, 카드: {mapping.membership_card.full_number}, 주유소: {station_name}')

if __name__ == '__main__':
    check_customer_relations() 