# Generated by Django 3.0 on 2020-09-01 06:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0199_auto_20200901_1051'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courierorder',
            name='number',
            field=models.CharField(max_length=20, unique=True),
        ),
    ]
