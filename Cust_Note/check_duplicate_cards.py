#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cust_Note.settings')
django.setup()

from Cust_StationApp.models import StationCardMapping

def check_duplicate_cards():
    # 특정 카드번호의 매핑 확인
    card_number = '8851111122223017'
    mappings = StationCardMapping.objects.filter(card__number=card_number)
    
    print(f"카드번호 {card_number}의 매핑 개수: {mappings.count()}")
    
    for mapping in mappings:
        print(f"ID: {mapping.id}")
        print(f"  Station: {mapping.station.username if mapping.station else 'None'}")
        print(f"  Active: {mapping.is_active}")
        print(f"  TID: {mapping.tid}")
        print(f"  Registered at: {mapping.registered_at}")
        print("---")
    
    # 모든 중복 카드 확인
    from django.db.models import Count
    duplicates = StationCardMapping.objects.values('card__number').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    print(f"\n중복된 카드 매핑이 있는 카드번호들:")
    for dup in duplicates:
        card_num = dup['card__number']
        count = dup['count']
        print(f"카드번호: {card_num}, 매핑 개수: {count}")

if __name__ == '__main__':
    check_duplicate_cards() 