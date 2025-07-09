from django.core.management.base import BaseCommand
from Cust_StationApp.models import PointCard

class Command(BaseCommand):
    help = '등록된 포인트카드 정보를 확인합니다.'

    def handle(self, *args, **options):
        try:
            # 전체 카드 수 확인
            total_cards = PointCard.objects.count()
            self.stdout.write(self.style.SUCCESS(f'전체 카드 수: {total_cards}'))

            # 사용중/미사용 카드 수 확인
            used_cards = PointCard.objects.filter(is_used=True).count()
            unused_cards = PointCard.objects.filter(is_used=False).count()
            self.stdout.write(self.style.SUCCESS(f'사용중인 카드: {used_cards}'))
            self.stdout.write(self.style.SUCCESS(f'미사용 카드: {unused_cards}'))

            # 최근 등록된 카드 10개 확인
            recent_cards = PointCard.objects.all().order_by('-created_at')[:10]
            if recent_cards:
                self.stdout.write('\n최근 등록된 카드 목록:')
                for card in recent_cards:
                    status = '사용중' if card.is_used else '미사용'
                    self.stdout.write(f'- {card.number} ({status}) - {card.created_at}')
            else:
                self.stdout.write(self.style.WARNING('등록된 카드가 없습니다.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'오류 발생: {str(e)}')) 