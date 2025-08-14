# Generated migration to remove max_issue_count field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('OilNote_StationApp', '0025_remove_first_time_only'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='autocoupontemplate',
            name='max_issue_count',
        ),
    ]