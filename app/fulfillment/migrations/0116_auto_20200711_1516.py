# Generated by Django 3.0 on 2020-07-11 11:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0115_auto_20200710_2332'),
    ]

    operations = [
        migrations.AddField(
            model_name='package',
            name='is_services',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='shipment',
            name='is_services',
            field=models.BooleanField(default=False),
        ),
    ]
