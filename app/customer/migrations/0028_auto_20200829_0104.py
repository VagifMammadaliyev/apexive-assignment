# Generated by Django 3.0 on 2020-08-28 21:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0027_auto_20200824_1838'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='recipient_id_pin',
            field=models.CharField(default='1234567', max_length=7),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='address',
            name='recipient_id_serial_number',
            field=models.CharField(default='AZE12345678', max_length=11),
            preserve_default=False,
        ),
    ]
