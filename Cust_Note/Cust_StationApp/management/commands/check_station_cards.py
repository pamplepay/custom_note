from django.core.management.base import BaseCommand
from Cust_StationApp.models import StationCardMapping
from Cust_User.models import CustomUser

class Command(BaseCommand):
    help = '주유소별 카드 매핑 정보를 확인합니다.'

    def handle(self, *args, **options):
        try:
            # 주유소 목록 조회
            stations = CustomUser.objects.filter(user_type='STATION')
            
            if not stations:
                self.stdout.write(self.style.WARNING('등록된 주유소가 없습니다.'))
                return
            
            for station in stations:
                self.stdout.write(self.style.SUCCESS(f'\n[{station.station_profile.station_name}] 주유소'))
                
                # 매핑된 카드 정보 조회
                mappings = StationCardMapping.objects.filter(station=station, is_active=True)
                total_cards = mappings.count()
                active_cards = mappings.filter(card__is_used=False).count()
                used_cards = mappings.filter(card__is_used=True).count()
                
                # 통계 출력
                self.stdout.write(f'전체 카드 수: {total_cards}')
                self.stdout.write(f'사용 가능 카드: {active_cards}')
                self.stdout.write(f'사용중인 카드: {used_cards}')
                
                # 최근 등록된 카드 5개 출력
                recent_mappings = mappings.select_related('card').order_by('-registered_at')[:5]
                if recent_mappings:
                    self.stdout.write('\n최근 등록된 카드:')
                    for mapping in recent_mappings:
                        status = '사용중' if mapping.card.is_used else '미사용'
                        self.stdout.write(f'- {mapping.card.number} ({status}) - {mapping.registered_at}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'오류 발생: {str(e)}')) 