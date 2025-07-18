#!/usr/bin/env python
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from Cust_User.models import CustomUser, CustomerProfile
from Cust_StationApp.models import PhoneCardMapping
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_phone_issue():
    """전화번호 저장 문제 디버깅"""
    print("=== 전화번호 저장 문제 디버깅 ===")
    
    # 1. netalf02 사용자 확인
    try:
        user = CustomUser.objects.get(username='netalf02')
        print(f"\n1. netalf02 사용자 정보:")
        print(f"   - 사용자명: {user.username}")
        print(f"   - 사용자 타입: {user.user_type}")
        print(f"   - 차량번호: {user.car_number}")
        
        # 고객 프로필 확인
        if hasattr(user, 'customer_profile'):
            profile = user.customer_profile
            print(f"   - 프로필 전화번호: {profile.customer_phone}")
            print(f"   - 프로필 차량번호: {profile.car_number}")
            print(f"   - 멤버십카드: {profile.membership_card}")
        else:
            print("   - 고객 프로필이 없습니다!")
            
    except CustomUser.DoesNotExist:
        print("netalf02 사용자가 존재하지 않습니다.")
        return
    
    # 2. 전화번호 매핑 정보 확인
    print(f"\n2. 전화번호 01012341234 매핑 정보:")
    phone_mappings = PhoneCardMapping.find_all_by_phone('01012341234')
    print(f"   - 총 매핑 수: {phone_mappings.count()}")
    
    for i, mapping in enumerate(phone_mappings, 1):
        print(f"   매핑 {i}:")
        print(f"     - 카드번호: {mapping.membership_card.full_number}")
        print(f"     - 주유소: {mapping.station.username}")
        print(f"     - 사용여부: {mapping.is_used}")
        print(f"     - 연동사용자: {mapping.linked_user.username if mapping.linked_user else '없음'}")
    
    # 3. CustomerSignUpForm의 save 메서드 시뮬레이션
    print(f"\n3. CustomerSignUpForm save 메서드 시뮬레이션:")
    
    # 폼 데이터 시뮬레이션
    phone = '01012341234'
    car_number = '12가3456'
    
    print(f"   - 입력된 전화번호: {phone}")
    print(f"   - 입력된 차량번호: {car_number}")
    
    # 프로필 업데이트 시뮬레이션
    if hasattr(user, 'customer_profile'):
        profile = user.customer_profile
        print(f"   - 업데이트 전 전화번호: {profile.customer_phone}")
        print(f"   - 업데이트 전 차량번호: {profile.car_number}")
        
        # 전화번호와 차량번호 업데이트
        if phone:
            profile.customer_phone = phone
        if car_number:
            profile.car_number = car_number
        
        profile.save()
        
        # 저장 후 확인
        profile.refresh_from_db()
        print(f"   - 업데이트 후 전화번호: {profile.customer_phone}")
        print(f"   - 업데이트 후 차량번호: {profile.car_number}")
    
    # 4. 시그널 확인
    print(f"\n4. 시그널 동작 확인:")
    print("   - post_save 시그널이 프로필을 덮어쓰는지 확인 필요")
    
    # 5. 모든 고객 프로필 확인
    print(f"\n5. 모든 고객 프로필 확인:")
    all_profiles = CustomerProfile.objects.all()
    print(f"   - 총 프로필 수: {all_profiles.count()}")
    
    for profile in all_profiles:
        print(f"   - {profile.user.username}: 전화번호={profile.customer_phone}, 차량번호={profile.car_number}")

if __name__ == '__main__':
    debug_phone_issue() 