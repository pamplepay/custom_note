# Generated migration for cumulative sales coupon improvements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('OilNote_StationApp', '0023_alter_autocoupontemplate_options_and_more'),
    ]

    operations = [
        # CumulativeSalesTracker 인덱스 추가 (성능 개선)
        migrations.AddIndex(
            model_name='cumulativesalestracker',
            index=models.Index(fields=['customer', 'station'], name='Cust_Station_cumulative_idx'),
        ),
        
        # AutoCouponTemplate 인덱스 개선
        migrations.AddIndex(
            model_name='autocoupontemplate',
            index=models.Index(fields=['station', 'coupon_type', 'is_active'], name='Cust_Station_auto_coupon_idx'),
        ),
    ]