# Generated by Django 3.1.2 on 2020-11-20 22:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0269_product_warehouseman_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shipment',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='shipment',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
