# Generated by Django 3.1.2 on 2021-01-06 11:18

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0291_shipment_is_deleted_from_smart_customs_by_us'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shipment',
            name='status_last_update_time',
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
    ]
