from django.core.management.base import BaseCommand
from excel_sample.views import process_sample_excel

class Command(BaseCommand):
    help = '샘플 엑셀 파일을 처리하여 데이터베이스에 저장합니다.'

    def handle(self, *args, **options):
        self.stdout.write('엑셀 파일 처리 시작...')
        process_sample_excel()
        self.stdout.write(self.style.SUCCESS('처리 완료!')) 