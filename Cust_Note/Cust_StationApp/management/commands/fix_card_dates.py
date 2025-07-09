from django.core.management.base import BaseCommand
from django.utils import timezone
from Cust_StationApp.models import PointCard
from datetime import datetime

class Command(BaseCommand):
    help = '미래 날짜로 등록된 카드들의 날짜를 현재 시간으로 수정합니다.'

    def handle(self, *args, **options):
        try:
            # 현재 시간 기준으로 미래에 등록된 카드 찾기
            now = timezone.now()
            future_cards = PointCard.objects.filter(created_at__gt=now)
            future_count = future_cards.count()
            
            if future_count == 0:
                self.stdout.write(self.style.SUCCESS('미래 날짜로 등록된 카드가 없습니다.'))
                return
            
            # 미래 날짜 카드들의 created_at을 현재 시간으로 수정
            future_cards.update(created_at=now)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'총 {future_count}개의 카드 날짜가 수정되었습니다.\n'
                    f'수정된 시간: {now.strftime("%Y-%m-%d %H:%M:%S")}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'카드 날짜 수정 중 오류가 발생했습니다: {str(e)}')
            ) 