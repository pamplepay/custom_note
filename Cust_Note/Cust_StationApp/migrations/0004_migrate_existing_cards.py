from django.db import migrations
from django.utils import timezone

def migrate_existing_cards(apps, schema_editor):
    PointCard = apps.get_model('Cust_StationApp', 'PointCard')
    StationCardMapping = apps.get_model('Cust_StationApp', 'StationCardMapping')
    CustomUser = apps.get_model('Cust_User', 'CustomUser')
    
    # 주유소 계정 찾기
    stations = CustomUser.objects.filter(user_type='STATION')
    if not stations.exists():
        return
    
    # 첫 번째 주유소를 기본 소유자로 설정
    default_station = stations.first()
    
    # 매핑되지 않은 카드들 찾기
    unmapped_cards = PointCard.objects.exclude(
        id__in=StationCardMapping.objects.values_list('card_id', flat=True)
    )
    
    # 매핑 생성
    mappings = []
    for card in unmapped_cards:
        mappings.append(
            StationCardMapping(
                station=default_station,
                card=card,
                registered_at=card.created_at,
                is_active=True
            )
        )
    
    if mappings:
        StationCardMapping.objects.bulk_create(mappings)

def reverse_migrate(apps, schema_editor):
    StationCardMapping = apps.get_model('Cust_StationApp', 'StationCardMapping')
    StationCardMapping.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('Cust_StationApp', '0003_stationcardmapping_pointcard_stations'),
        ('Cust_User', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_existing_cards, reverse_migrate),
    ] 