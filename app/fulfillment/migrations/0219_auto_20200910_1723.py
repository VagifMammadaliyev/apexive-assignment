# Generated by Django 3.1.1 on 2020-09-10 13:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0218_auto_20200909_2356'),
    ]

    operations = [
        migrations.AlterField(
            model_name='warehouse',
            name='address',
            field=models.CharField(max_length=500),
        ),
    ]
