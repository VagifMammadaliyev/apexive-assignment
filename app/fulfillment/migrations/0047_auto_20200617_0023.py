# Generated by Django 3.0 on 2020-06-16 20:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0046_auto_20200616_2340'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='external_order_code',
            field=models.CharField(blank=True, db_index=True, max_length=20, null=True),
        ),
    ]
