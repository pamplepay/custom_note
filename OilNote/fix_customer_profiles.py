#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_User.models import CustomUser, CustomerProfile

def fix_customer_profiles():
    print('=== 고객 프로필 수정 시작 ===')
    
    # 모든 고객 사용자 확인
    customers = CustomUser.objects.filter(user_type='CUSTOMER')
    print(f'총 고객 수: {customers.count()}')
    
    for customer in customers:
        try:
            profile = customer.customer_profile
            updated = False
            
            print(f'\n사용자: {customer.username}')
            print(f'  - 기존 전화번호: {profile.customer_phone or "없음"}')
            print(f'  - 기존 차량번호: {profile.car_number or "없음"}')
            print(f'  - CustomUser.car_number: {customer.car_number or "없음"}')
            
            # CustomUser의 car_number를 CustomerProfile로 복사
            if customer.car_number and not profile.car_number:
                profile.car_number = customer.car_number
                updated = True
                print(f'  - 차량번호 업데이트: {customer.car_number}')
            
            # netalf02 사용자의 경우 전화번호도 설정
            if customer.username == 'netalf02' and not profile.customer_phone:
                profile.customer_phone = '01012341234'
                updated = True
                print(f'  - 전화번호 업데이트: 01012341234')
            
            if updated:
                profile.save()
                print(f'  - 프로필 저장 완료')
            else:
                print(f'  - 업데이트 불필요')
                
        except Exception as e:
            print(f'사용자: {customer.username} - 프로필 수정 실패: {e}')
    
    print('\n=== 수정 후 확인 ===')
    for customer in customers:
        try:
            profile = customer.customer_profile
            print(f'\n사용자: {customer.username}')
            print(f'  - 전화번호: {profile.customer_phone or "없음"}')
            print(f'  - 차량번호: {profile.car_number or "없음"}')
            print(f'  - 멤버십카드: {profile.membership_card or "없음"}')
        except Exception as e:
            print(f'사용자: {customer.username} - 확인 실패: {e}')

if __name__ == '__main__':
    fix_customer_profiles() 