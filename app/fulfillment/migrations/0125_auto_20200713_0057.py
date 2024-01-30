# Generated by Django 3.0 on 2020-07-12 20:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0124_warehouse_is_consolidation_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='packageadditionalservice',
            name='is_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='shipmentadditionalservice',
            name='is_completed',
            field=models.BooleanField(default=False),
        ),
    ]