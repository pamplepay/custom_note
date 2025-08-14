#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_User.models import CustomUser, CustomerProfile
from OilNote_StationApp.models import PhoneCardMapping, PointCard

def fix_data():
    print('=== 데이터 수정 시작 ===')
    
    # 1. netalf02 사용자의 전화번호 설정
    try:
        user = CustomUser.objects.get(username='netalf02')
        profile = user.customer_profile
        profile.customer_phone = '01012341234'
        profile.save()
        print(f'netalf02 사용자 전화번호를 01012341234로 설정했습니다.')
    except Exception as e:
        print(f'netalf02 사용자 수정 실패: {e}')
    
    # 2. 01012341234 전화번호의 PhoneCardMapping 확인 및 수정
    phone_mappings = PhoneCardMapping.objects.filter(phone_number='01012341234')
    print(f'\n전화번호 01012341234 매핑 수: {phone_mappings.count()}')
    
    for mapping in phone_mappings:
        print(f'매핑 ID: {mapping.id}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {mapping.linked_user.username if mapping.linked_user else "없음"}')
        
        # 사용 중이지만 연동된 사용자가 없는 경우 수정
        if mapping.is_used and not mapping.linked_user:
            try:
                # netalf02 사용자와 연동
                user = CustomUser.objects.get(username='netalf02')
                mapping.linked_user = user
                mapping.save()
                print(f'매핑 ID {mapping.id}를 netalf02 사용자와 연동했습니다.')
            except Exception as e:
                print(f'매핑 ID {mapping.id} 연동 실패: {e}')
    
    # 3. 고객 프로필의 멤버십카드 정보 업데이트
    try:
        user = CustomUser.objects.get(username='netalf02')
        profile = user.customer_profile
        
        # 연동된 카드들 가져오기
        linked_mappings = PhoneCardMapping.objects.filter(
            phone_number='01012341234',
            linked_user=user
        )
        
        if linked_mappings.exists():
            card_numbers = [mapping.membership_card.full_number for mapping in linked_mappings]
            profile.membership_card = ','.join(card_numbers)
            profile.save()
            print(f'netalf02 사용자의 멤버십카드를 {profile.membership_card}로 업데이트했습니다.')
        else:
            print('연동된 멤버십카드가 없습니다.')
            
    except Exception as e:
        print(f'멤버십카드 업데이트 실패: {e}')
    
    print('\n=== 수정 후 데이터 확인 ===')
    try:
        user = CustomUser.objects.get(username='netalf02')
        profile = user.customer_profile
        print(f'netalf02 - 전화번호: {profile.customer_phone}, 멤버십카드: {profile.membership_card}')
    except Exception as e:
        print(f'확인 실패: {e}')

if __name__ == '__main__':
    fix_data() 