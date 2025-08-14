#!/usr/bin/env python3
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OilNote.settings')
django.setup()

from OilNote_StationApp.models import StationCardMapping
from django.db.models import Count

def clean_duplicate_cards():
    """중복된 카드 매핑을 정리합니다."""
    
    # 중복된 카드 매핑 찾기
    duplicates = StationCardMapping.objects.values('card__number').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    print(f"중복된 카드 매핑이 있는 카드번호들:")
    for dup in duplicates:
        card_num = dup['card__number']
        count = dup['count']
        print(f"카드번호: {card_num}, 매핑 개수: {count}")
        
        # 각 중복 카드의 상세 정보 확인
        mappings = StationCardMapping.objects.filter(card__number=card_num).order_by('id')
        print(f"  상세 정보:")
        for mapping in mappings:
            print(f"    ID: {mapping.id}, Station: {mapping.station.username if mapping.station else 'None'}, Active: {mapping.is_active}, TID: {mapping.tid}")
        
        # 중복 정리 (첫 번째 것만 남기고 나머지 삭제)
        if count > 1:
            first_mapping = mappings.first()
            duplicate_mappings = mappings.exclude(id=first_mapping.id)
            
            print(f"  정리: ID {first_mapping.id} 유지, 나머지 {duplicate_mappings.count()}개 삭제")
            
            # 실제 삭제 (주석 처리되어 있음)
            # duplicate_mappings.delete()
            # print(f"  삭제 완료")
            
            print("  (실제 삭제는 주석 처리되어 있음)")

if __name__ == '__main__':
    clean_duplicate_cards() 