# Generated by Django 3.1.2 on 2020-12-21 06:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0284_auto_20201221_1048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='promocode',
            name='value',
            field=models.CharField(max_length=20, unique=True),
        ),
    ]
