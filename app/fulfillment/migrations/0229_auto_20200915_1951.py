# Generated by Django 3.1.1 on 2020-09-15 15:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0228_warehouse_airport_city'),
    ]

    operations = [
        migrations.AlterField(
            model_name='package',
            name='weight',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=9, null=True),
        ),
        migrations.AlterField(
            model_name='shipment',
            name='fixed_total_weight',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=9),
        ),
    ]
