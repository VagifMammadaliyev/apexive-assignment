# Generated by Django 3.0 on 2020-06-29 20:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0082_shipment_is_dangerous'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='fixed_total_weight',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9),
        ),
    ]
