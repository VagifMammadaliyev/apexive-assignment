# Generated by Django 3.0 on 2020-06-29 20:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0081_package_shelf'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='is_dangerous',
            field=models.BooleanField(default=False),
        ),
    ]
