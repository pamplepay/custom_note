#!/usr/bin/env python
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from Cust_User.forms import CustomerSignUpForm
from Cust_User.models import CustomUser, CustomerProfile
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_signup_process():
    """회원가입 과정 테스트"""
    print("=== 회원가입 과정 테스트 ===")
    
    # 테스트 데이터
    test_data = {
        'username': 'testuser123',
        'email': 'test@example.com',
        'password1': 'TestPass123!',
        'password2': 'TestPass123!',
        'user_type': 'CUSTOMER',
        'customer_phone': '01012341234',
        'car_number': '12가3456'
    }
    
    print(f"테스트 데이터: {test_data}")
    
    # 폼 생성 및 검증
    form = CustomerSignUpForm(data=test_data)
    
    if form.is_valid():
        print("✓ 폼 검증 성공")
        print(f"  - cleaned_data: {form.cleaned_data}")
        
        # 사용자 생성
        user = form.save()
        print(f"✓ 사용자 생성 완료: {user.username}")
        
        # 프로필 확인
        if hasattr(user, 'customer_profile'):
            profile = user.customer_profile
            print(f"✓ 프로필 확인:")
            print(f"  - 전화번호: {profile.customer_phone}")
            print(f"  - 차량번호: {profile.car_number}")
            print(f"  - 멤버십카드: {profile.membership_card}")
        else:
            print("✗ 프로필이 생성되지 않음")
        
        # 테스트 사용자 삭제
        user.delete()
        print("✓ 테스트 사용자 삭제 완료")
        
    else:
        print("✗ 폼 검증 실패")
        print(f"  - 오류: {form.errors}")
    
    # 기존 사용자 확인
    print(f"\n=== 기존 사용자 확인 ===")
    try:
        user = CustomUser.objects.get(username='netalf02')
        if hasattr(user, 'customer_profile'):
            profile = user.customer_profile
            print(f"netalf02 프로필:")
            print(f"  - 전화번호: {profile.customer_phone}")
            print(f"  - 차량번호: {profile.car_number}")
            print(f"  - 멤버십카드: {profile.membership_card}")
    except CustomUser.DoesNotExist:
        print("netalf02 사용자가 존재하지 않습니다.")

if __name__ == '__main__':
    test_signup_process() 