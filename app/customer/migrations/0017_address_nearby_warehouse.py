# Generated by Django 3.0 on 2020-06-20 10:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0054_shipment_is_paid'),
        ('customer', '0016_auto_20200620_1354'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='nearby_warehouse',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='user_addresses', related_query_name='user_address', to='fulfillment.Warehouse'),
            preserve_default=False,
        ),
    ]
