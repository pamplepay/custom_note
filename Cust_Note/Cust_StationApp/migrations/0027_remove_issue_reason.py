# Generated migration to remove issue_reason field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Cust_StationApp', '0026_remove_max_issue_count'),
    ]

    operations = [
        # issue_reason 필드가 이미 제거됨 - 빈 마이그레이션
    ]