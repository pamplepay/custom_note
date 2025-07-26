# Generated migration to remove first_time_only references

from django.db import migrations


def remove_first_time_only_from_condition_data(apps, schema_editor):
    """
    AutoCouponTemplate의 condition_data에서 first_time_only 키 제거
    """
    AutoCouponTemplate = apps.get_model('Cust_StationApp', 'AutoCouponTemplate')
    
    for template in AutoCouponTemplate.objects.all():
        if template.condition_data and isinstance(template.condition_data, dict):
            if 'first_time_only' in template.condition_data:
                condition_data = template.condition_data.copy()
                condition_data.pop('first_time_only', None)
                template.condition_data = condition_data
                template.save()


def reverse_remove_first_time_only(apps, schema_editor):
    """
    Reverse migration - first_time_only는 복원하지 않음
    이 기능은 누적매출 쿠폰에 불필요한 기능이므로 복원하지 않습니다.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('Cust_StationApp', '0024_auto_cumulative_improvements'),
    ]

    operations = [
        migrations.RunPython(
            remove_first_time_only_from_condition_data,
            reverse_remove_first_time_only,
        ),
    ]