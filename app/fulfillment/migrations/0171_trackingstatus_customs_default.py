# Generated by Django 3.0 on 2020-08-19 21:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0170_shipment_tracking_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='trackingstatus',
            name='customs_default',
            field=models.BooleanField(default=False),
        ),
    ]