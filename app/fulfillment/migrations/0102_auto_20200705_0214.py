# Generated by Django 3.0 on 2020-07-04 22:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0101_auto_20200705_0005'),
    ]

    operations = [
        migrations.AlterField(
            model_name='box',
            name='code',
            field=models.CharField(max_length=255),
        ),
    ]
