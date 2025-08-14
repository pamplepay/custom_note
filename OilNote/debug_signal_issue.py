#!/usr/bin/env python
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_User.models import CustomUser, CustomerProfile
from OilNote_User.signals import create_user_profile, save_user_profile
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_signal_issue():
    """시그널이 프로필을 덮어쓰는지 확인"""
    print("=== 시그널 덮어쓰기 문제 디버깅 ===")
    
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
    
    # 2. 시그널 동작 시뮬레이션
    print(f"\n2. 시그널 동작 시뮬레이션:")
    
    # save_user_profile 시그널 시뮬레이션
    print("   - save_user_profile 시그널 호출:")
    save_user_profile(sender=CustomUser, instance=user)
    
    # 프로필 다시 확인
    if hasattr(user, 'customer_profile'):
        profile = user.customer_profile
        profile.refresh_from_db()
        print(f"   - 시그널 후 전화번호: {profile.customer_phone}")
        print(f"   - 시그널 후 차량번호: {profile.car_number}")
    
    # 3. 사용자 저장 시뮬레이션
    print(f"\n3. 사용자 저장 시뮬레이션:")
    
    # 전화번호를 다시 설정
    if hasattr(user, 'customer_profile'):
        profile = user.customer_profile
        profile.customer_phone = '01012341234'
        profile.car_number = '23더1025'
        profile.save()
        print(f"   - 프로필 업데이트 후 전화번호: {profile.customer_phone}")
        print(f"   - 프로필 업데이트 후 차량번호: {profile.car_number}")
    
    # 사용자 저장 (시그널 트리거)
    user.save()
    print("   - 사용자 저장 완료 (시그널 트리거됨)")
    
    # 저장 후 프로필 확인
    if hasattr(user, 'customer_profile'):
        profile = user.customer_profile
        profile.refresh_from_db()
        print(f"   - 사용자 저장 후 전화번호: {profile.customer_phone}")
        print(f"   - 사용자 저장 후 차량번호: {profile.car_number}")
    
    # 4. 시그널 코드 분석
    print(f"\n4. 시그널 코드 분석:")
    print("   - create_user_profile: 프로필 생성 시에만 동작")
    print("   - save_user_profile: 사용자 저장 시마다 동작")
    print("   - save_user_profile에서 프로필 데이터를 덮어쓰는지 확인 필요")

if __name__ == '__main__':
    debug_signal_issue() 