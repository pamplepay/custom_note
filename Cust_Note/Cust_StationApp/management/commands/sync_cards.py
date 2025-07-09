from django.core.management.base import BaseCommand
from django.utils import timezone
from Cust_StationApp.models import PointCard, StationCardMapping
from Cust_User.models import CustomUser

class Command(BaseCommand):
    help = '실제 서버의 포인트카드 정보와 동기화합니다.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('이 명령어는 더 이상 사용되지 않습니다. 주유소 관리 페이지에서 카드를 등록해주세요.')) 