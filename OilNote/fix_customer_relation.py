#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_User.models import CustomUser, CustomerProfile
from OilNote_StationApp.models import PhoneCardMapping, PointCard

def fix_customer_relation():
    print('=== 고객 연동 문제 해결 시작 ===')
    
    # 1. netalf02 사용자 찾기
    try:
        user = CustomUser.objects.get(username='netalf02')
        print(f'사용자 찾음: {user.username}')
    except CustomUser.DoesNotExist:
        print('netalf02 사용자를 찾을 수 없습니다.')
        return
    
    # 2. netalf02 사용자의 프로필에 전화번호 설정
    profile = user.customer_profile
    profile.customer_phone = '01012341234'
    profile.save()
    print(f'netalf02 사용자 전화번호를 01012341234로 설정했습니다.')
    
    # 3. 전화번호 01012341234의 PhoneCardMapping 확인
    phone_mappings = PhoneCardMapping.objects.filter(phone_number='01012341234')
    print(f'\n전화번호 01012341234 매핑 수: {phone_mappings.count()}')
    
    for mapping in phone_mappings:
        print(f'매핑 ID: {mapping.id}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {mapping.linked_user.username if mapping.linked_user else "없음"}')
            
        # 사용 중이지만 연동된 사용자가 없는 경우 수정
        if mapping.is_used and not mapping.linked_user:
            try:
                mapping.linked_user = user
                mapping.save()
                print(f'매핑 ID {mapping.id}를 netalf02 사용자와 연동했습니다.')
            except Exception as e:
                print(f'매핑 ID {mapping.id} 연동 실패: {e}')
        
        # 미사용 상태인 경우 연동
        elif not mapping.is_used:
            try:
                mapping.link_to_user(user)
                print(f'매핑 ID {mapping.id}를 netalf02 사용자와 연동했습니다.')
    except Exception as e:
                print(f'매핑 ID {mapping.id} 연동 실패: {e}')
    
    # 4. 연동 결과 확인
    print('\n=== 연동 결과 확인 ===')
    profile = user.customer_profile
    print(f'netalf02 사용자 전화번호: {profile.customer_phone}')
    print(f'netalf02 사용자 멤버십카드: {profile.membership_card}')
    
    phone_mappings = PhoneCardMapping.objects.filter(phone_number='01012341234')
    for mapping in phone_mappings:
        linked_user = mapping.linked_user.username if mapping.linked_user else "없음"
        print(f'매핑 ID: {mapping.id}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {linked_user}')
    
    print('\n=== 고객 연동 문제 해결 완료 ===')

if __name__ == '__main__':
    fix_customer_relation() 