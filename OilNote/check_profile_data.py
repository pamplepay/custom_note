#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_User.models import CustomUser, CustomerProfile

def check_profile_data():
    print('=== 고객 프로필 데이터 확인 ===')
    
    # 모든 고객 사용자 확인
    customers = CustomUser.objects.filter(user_type='CUSTOMER')
    print(f'총 고객 수: {customers.count()}')
    
    for customer in customers:
        try:
            profile = customer.customer_profile
            print(f'\n사용자: {customer.username}')
            print(f'  - 전화번호: {profile.customer_phone or "없음"}')
            print(f'  - 차량번호: {profile.car_number or "없음"}')
            print(f'  - 멤버십카드: {profile.membership_card or "없음"}')
            print(f'  - 이름: {profile.name or "없음"}')
            print(f'  - 프로필 생성일: {profile.created_at}')
            print(f'  - 프로필 수정일: {profile.updated_at}')
        except Exception as e:
            print(f'사용자: {customer.username} - 프로필 오류: {e}')
    
    # netalf02 사용자 특별 확인
    print('\n=== netalf02 사용자 상세 확인 ===')
    try:
        user = CustomUser.objects.get(username='netalf02')
        profile = user.customer_profile
        print(f'사용자: {user.username}')
        print(f'  - 전화번호: {profile.customer_phone or "없음"}')
        print(f'  - 차량번호: {profile.car_number or "없음"}')
        print(f'  - 멤버십카드: {profile.membership_card or "없음"}')
        print(f'  - 이름: {profile.name or "없음"}')
        print(f'  - 프로필 생성일: {profile.created_at}')
        print(f'  - 프로필 수정일: {profile.updated_at}')
        
        # CustomUser 모델의 car_number 필드도 확인
        print(f'  - CustomUser.car_number: {user.car_number or "없음"}')
        
    except Exception as e:
        print(f'netalf02 사용자 확인 실패: {e}')

if __name__ == '__main__':
    check_profile_data() 