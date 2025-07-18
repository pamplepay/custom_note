#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from Cust_User.models import CustomUser, CustomerProfile
from Cust_StationApp.models import PhoneCardMapping, PointCard

def check_data():
    print('=== 고객 사용자 목록 ===')
    customers = CustomUser.objects.filter(user_type='CUSTOMER')
    print(f'총 고객 수: {customers.count()}')
    
    for customer in customers:
        try:
            profile = customer.customer_profile
            phone = getattr(profile, 'customer_phone', '없음')
            membership_card = getattr(profile, 'membership_card', '없음')
            print(f'ID: {customer.id}, 사용자명: {customer.username}, 전화번호: {phone}, 멤버십카드: {membership_card}')
        except Exception as e:
            print(f'ID: {customer.id}, 사용자명: {customer.username}, 프로필 오류: {e}')

    print('\n=== 전화번호 01012341234 관련 데이터 ===')
    phone_mappings = PhoneCardMapping.objects.filter(phone_number='01012341234')
    print(f'전화번호 01012341234 매핑 수: {phone_mappings.count()}')
    
    for mapping in phone_mappings:
        linked_user = mapping.linked_user.username if mapping.linked_user else "없음"
        print(f'매핑 ID: {mapping.id}, 카드: {mapping.membership_card.full_number}, 사용여부: {mapping.is_used}, 연동사용자: {linked_user}')

    print('\n=== 멤버십카드 상태 ===')
    cards = PointCard.objects.all()
    print(f'총 카드 수: {cards.count()}')
    
    for card in cards:
        print(f'카드: {card.full_number}, 사용여부: {card.is_used}')

    print('\n=== 최근 고객 등록 확인 ===')
    recent_customers = customers.order_by('-date_joined')[:5]
    for customer in recent_customers:
        try:
            profile = customer.customer_profile
            phone = getattr(profile, 'customer_phone', '없음')
            print(f'최근 등록: {customer.username} (전화번호: {phone}) - {customer.date_joined}')
        except Exception as e:
            print(f'최근 등록: {customer.username} - {customer.date_joined} (프로필 오류: {e})')

if __name__ == '__main__':
    check_data() 